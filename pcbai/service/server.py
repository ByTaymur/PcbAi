import json
import os
import secrets
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pcbai import __version__
from pcbai.config import state_directory, write_json
from pcbai.core.contract import PcbAiError
from pcbai.tools.engine import Engine
from pcbai.service.handoff import Handoffs
from pcbai.service.sessions import Sessions
from pcbai.service.agent_prompt import PromptError, serve_prompt


@contextmanager
def singleton(state):
    stream = (state / "service.lock").open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            try:
                # Another process can lock byte zero, including reads. Keep initialization in this guard.
                stream.seek(0)
                if not stream.read(1):
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise PcbAiError("service_running", "A PcbAi service already holds this state directory") from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise PcbAiError("service_running", "A PcbAi service already holds this state directory") from exc
        yield
    finally:
        stream.close()


class Server(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False


def handler(engine, token, instance):
    handoffs = Handoffs(engine.state)

    def handoff_call(path, payload):
        """KiCad → VS Code handoff (AJ-5); internal endpoints, not MCP tools."""
        if path == "/handoff/create":
            if not isinstance(payload.get("session"), str):
                raise PcbAiError("invalid_arguments", "session gerekli")
            session = engine.sessions.get(payload["session"])
            return dict(ok=True, id=handoffs.create(session, payload.get("prompt")))
        if path == "/handoff/take":
            return dict(ok=True, **handoffs.take(payload.get("id")))
        if path == "/handoff/report":
            return handoffs.report(payload.get("id"), payload.get("outcome"), payload.get("message", ""))
        return dict(ok=True, **handoffs.status(payload.get("id")))

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *_args):
            pass

        def reply(self, status, payload):
            data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)

        def body(self):
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("Transfer-Encoding is unsupported")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1024 * 1024:
                raise ValueError("Invalid body length")
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("Incomplete request")
            return json.loads(raw)

        def authorized(self):
            provided = self.headers.get("Authorization", "")
            host = self.headers.get("Host", "")
            if self.headers.get("Origin") or host != f"127.0.0.1:{self.server.server_port}":
                self.reply(403, {"error": "Browser origins and non-loopback Host are rejected"})
                return False
            if not secrets.compare_digest(provided.encode(), ("Bearer " + token).encode()):
                self.reply(401, {"error": "Authentication required"})
                return False
            return True

        def do_GET(self):
            if not self.authorized():
                return
            if self.path == "/health":
                self.reply(200, dict(ok=True, name="pcbai", version=__version__, instance=instance,
                                     pid=os.getpid(), projects=sorted(str(s.root / s.project)
                                     for s in engine.sessions.entries.values())))
            elif self.path == "/tools":
                self.reply(200, {"tools": engine.definitions})
            elif self.path == "/events" or self.path.startswith("/events?since="):
                since = self.path.partition("=")[2]
                if since and not since.isdigit():
                    self.reply(400, {"error": "since must be an event sequence number"})
                    return
                self.reply(200, {"events": engine.recent_events(int(since) if since else None)})
            elif self.path == "/version":
                self.reply(200, {"version": __version__, "sessions": engine.sessions.describe()})
            else:
                self.reply(404, {"error": "Unknown endpoint"})

        def do_POST(self):
            if not self.authorized():
                return
            if self.path == "/shutdown":
                self.reply(200, {"ok": True, "instance": instance})

                def stop_safely():
                    engine.stopping = True
                    engine.jobs.close()
                    locks = [session.lock for session in engine.sessions.entries.values()]
                    for lock in locks:
                        lock.acquire()
                    try:
                        self.server.shutdown()
                    finally:
                        for lock in reversed(locks):
                            lock.release()

                threading.Thread(target=stop_safely, daemon=True).start()
                return
            if self.path in {"/handoff/create", "/handoff/take", "/handoff/report", "/handoff/status"}:
                try:
                    payload = self.body()
                    if not isinstance(payload, dict):
                        raise ValueError("Expected an object")
                except (ValueError, OSError) as exc:
                    self.reply(400, {"error": str(exc)})
                    return
                try:
                    self.reply(200, handoff_call(self.path, payload))
                except PcbAiError as exc:
                    self.reply(200, dict(ok=False, error=dict(code=exc.code, message=str(exc))))
                except Exception:
                    self.reply(500, {"error": "Internal service error"})
                return
            if self.path not in {"/call", "/view/call", "/agent/prompt"}:
                self.reply(404, {"error": "Unknown endpoint"})
                return
            try:
                if self.headers.get("Transfer-Encoding"):
                    raise ValueError("Transfer-Encoding is unsupported")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024 * 1024:
                    raise ValueError("Invalid body length")
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError("Incomplete request")
                payload = json.loads(raw)
                if self.path == "/agent/prompt":
                    # Internal call for the extension and KiCad window; deliberately not an MCP tool.
                    if not isinstance(payload, dict):
                        raise ValueError("Expected an object")
                    try:
                        self.reply(200, dict(ok=True, prompt=serve_prompt(engine, payload)))
                    except (PromptError, PcbAiError) as exc:
                        self.reply(200, dict(ok=False, error=dict(code=getattr(exc, "code", "invalid_request"),
                                                                  message=str(exc))))
                    except Exception:
                        self.reply(500, {"error": "Internal service error"})
                    return
                if not isinstance(payload, dict) or set(payload) != {"name", "arguments"}:
                    raise ValueError("Expected name and arguments")
                if not isinstance(payload["name"], str) or not isinstance(payload["arguments"], dict):
                    raise ValueError("Invalid call parameters")
            except (ValueError, OSError) as exc:
                self.reply(400, {"error": str(exc)})
                return
            try:
                self.reply(200, engine.call(payload["name"], payload["arguments"],
                                           source="view" if self.path == "/view/call" else "tool",
                                           client=self.headers.get("X-PcbAi-Client", "")[:80]))
            except Exception:
                self.reply(500, {"error": "Internal service error"})

    return Handler


def serve(projects, *, stop=None):
    projects = list(projects)
    registered = Sessions(projects)
    state = state_directory(s.root for s in registered.entries.values())
    with singleton(state):
        engine = Engine(projects, state)
        token, instance = secrets.token_urlsafe(32), secrets.token_hex(16)
        server = Server(("127.0.0.1", 0), handler(engine, token, instance))
        info = dict(port=server.server_port, token=token, pid=os.getpid(), instance=instance,
                    version=__version__, projects=sorted(str(s.root / s.project)
                    for s in engine.sessions.entries.values()))
        identity = state / "service.json"
        write_json(identity, info)
        if stop is not None:
            def watch_stop():
                stop.wait()
                server.shutdown()
            threading.Thread(target=watch_stop, daemon=True).start()
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
        finally:
            engine.stopping = True
            engine.jobs.close()
            server.server_close()
            try:
                current = json.loads(identity.read_text(encoding="utf-8"))
                if current.get("instance") == instance:
                    identity.unlink()
            except (OSError, ValueError):
                pass
