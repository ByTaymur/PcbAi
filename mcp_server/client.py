"""Stdlib-only client, compatible with Python 3.9+. Never retries a tool mutation."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

NO_PROJECT = ("PcbAi servisi çalışmıyor ve bu MCP kaydında proje yok. KiCad'de PcbAi'ye kaydet'e basın ya da "
              "VS Code'da projeyi seçin, sonra yeniden deneyin.")


class ServiceUnavailable(RuntimeError):
    """User-level registrations carry no PCBAI_PROJECTS: without a running service there is nothing to open."""


class Client:
    def __init__(self):
        base = os.environ.get("PCBAI_STATE_DIR")
        self.state = Path(base) if base else Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "PcbAi"
        self.projects = [str(Path(p).expanduser().resolve()) for p in json.loads(os.environ.get("PCBAI_PROJECTS", "[]"))]
        self.info = None
        # Reported identity for the activity log only (vscode, kicad, mcp:<clientInfo.name>); grants nothing.
        self.client_name = ""
        self.opener = build_opener(ProxyHandler({}))

    def _request(self, method, path, payload=None, timeout=150):
        info = self.info
        port = info["port"]
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise ValueError("Invalid local service port")
        token = info["token"]
        if not isinstance(token, str) or len(token) < 32 or "\n" in token or "\r" in token:
            raise ValueError("Invalid service token")
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(f"http://127.0.0.1:{port}{path}", data=data, method=method,
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                                   **({"X-PcbAi-Client": self.client_name} if self.client_name else {})})
        with self.opener.open(request, timeout=timeout) as response:
            return json.load(response)

    def connect(self):
        try:
            self.info = json.loads((self.state / "service.json").read_text(encoding="utf-8"))
            health = self._request("GET", "/health", timeout=2)
            if health.get("name") != "pcbai" or health.get("instance") != self.info.get("instance"):
                raise ValueError("Service identity mismatch")
            if self.missing(health):
                raise RuntimeError("Service has different registered projects. Stop it, then start with PCBAI_PROJECTS.")
            return
        except RuntimeError:
            raise
        except (OSError, ValueError, KeyError):
            self.info = None
        if not self.projects:
            raise ServiceUnavailable(NO_PROJECT)
        root = Path(__file__).resolve().parents[1]
        bundled = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        python = os.environ.get("PCBAI_SERVICE_PYTHON") or (str(bundled) if bundled.is_file() else sys.executable)
        argv = [python, "-m", "pcbai", "serve"]
        for project in self.projects:
            argv.extend(["--project", project])
        process = subprocess.Popen(argv, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, shell=False,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        deadline = time.monotonic() + 12
        try:
            while time.monotonic() < deadline:
                try:
                    self.info = json.loads((self.state / "service.json").read_text(encoding="utf-8"))
                    health = self._request("GET", "/health", timeout=1)
                    if health.get("name") == "pcbai" and health.get("instance") == self.info.get("instance"):
                        if self.missing(health):
                            raise RuntimeError("Service has different registered projects")
                        return
                except (OSError, ValueError, KeyError):
                    pass
                time.sleep(0.1)
            raise RuntimeError("PcbAi service could not start. Run python -m pcbai serve to see the error.")
        finally:
            # Keep an owned process reference; the service deliberately outlives the MCP connection.
            self.started_process = process

    def missing(self, health):
        """Wanted projects the service has not registered. A service may hold more projects (VS Code, KiCad
        plugin and several agents share one service); every one of them was registered explicitly."""
        def key(path):
            return os.path.normcase(os.path.normpath(path))
        registered = {key(p) for p in health.get("projects", [])}
        return [p for p in self.projects if key(p) not in registered]

    def request(self, method, path, payload=None):
        self.connect()
        return self._request(method, path, payload)

    def shutdown(self):
        """Stop only an authenticated, already running service; never auto-start."""
        try:
            self.info = json.loads((self.state / "service.json").read_text(encoding="utf-8"))
            health = self._request("GET", "/health", timeout=2)
            if health.get("name") != "pcbai" or health.get("instance") != self.info.get("instance"):
                raise RuntimeError("Service identity mismatch")
            return self._request("POST", "/shutdown", {}, timeout=2)
        except (OSError, ValueError, KeyError):
            return {"ok": True, "already_stopped": True}
