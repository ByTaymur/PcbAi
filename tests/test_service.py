import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from tests.helpers import make_project
from mcp_server.client import Client


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pcbai-service-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.project = make_project(self.root / "project")
        self.env = dict(os.environ, PCBAI_STATE_DIR=str(self.state), PCBAI_PROJECTS=json.dumps([str(self.project)]))
        self.service = self.start([sys.executable, "-m", "pcbai", "serve", "--project", str(self.project)])
        self.addCleanup(self.stop)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                self.info = json.loads((self.state / "service.json").read_text(encoding="utf-8"))
                break
            except (OSError, ValueError):
                if self.service.poll() is not None:
                    self.fail(self.service.stderr.read().decode())
                time.sleep(0.05)
        else:
            self.fail("Service startup timed out")
        self.opener = build_opener(ProxyHandler({}))

    def start(self, argv):
        return subprocess.Popen(argv, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

    def stop(self):
        try:
            if self.service.poll() is None and hasattr(self, "opener"):
                self.request("/shutdown", payload={})
                self.service.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if self.service.poll() is None:
            self.service.terminate()
        self.service.communicate(timeout=10)
        for stream in (self.service.stdout, self.service.stderr):
            stream.close()

    def request(self, path, *, token=None, payload=None, headers=None):
        auth = {"Authorization": "Bearer " + (token if token is not None else self.info["token"])}
        auth.update(headers or {})
        body = None if payload is None else json.dumps(payload).encode()
        request = Request(f"http://127.0.0.1:{self.info['port']}{path}", data=body, headers=auth)
        with self.opener.open(request, timeout=10) as response:
            return json.load(response)

    def test_kicad_to_vscode_handoff_endpoints(self):
        session = self.request("/call", payload={"name": "pcbai_status", "arguments": {}})["sessions"][0]["id"]
        created = self.request("/handoff/create", payload={"session": session, "prompt": "R5 değerini oku"})
        self.assertTrue(created["ok"])
        handoff_id = created["id"]
        taken = self.request("/handoff/take", payload={"id": handoff_id})
        self.assertEqual(taken["prompt"], "R5 değerini oku")
        self.assertEqual(self.request("/handoff/take", payload={"id": handoff_id})["error"]["code"], "already_taken")
        self.assertTrue(self.request("/handoff/report", payload={"id": handoff_id, "outcome": "typed",
                                                                  "message": "yazıldı"})["ok"])
        status = self.request("/handoff/status", payload={"id": handoff_id})
        self.assertEqual((status["outcome"], status["message"]), ("typed", "yazıldı"))
        self.assertEqual(self.request("/handoff/create", payload={"session": {"x": 1}, "prompt": "p"})["error"]["code"],
                         "invalid_arguments")
        self.assertEqual(self.request("/handoff/create", payload={"session": "nope", "prompt": "p"})["error"]["code"],
                         "unknown_session")
        with self.assertRaises(HTTPError) as caught:
            self.request("/handoff/take", token="wrong", payload={"id": handoff_id})
        self.assertEqual(caught.exception.code, 401)
        caught.exception.close()
        tools = self.request("/tools")["tools"]
        self.assertFalse(any("handoff" in tool["name"] for tool in tools))

    def test_auth_origin_and_host_rejection(self):
        for token, headers, code in [("wrong", {}, 401), (None, {"Origin": "https://evil.test"}, 403),
                                     (None, {"Host": "evil.test"}, 403)]:
            with self.subTest(code=code), self.assertRaises(HTTPError) as caught:
                self.request("/health", token=token, headers=headers)
            self.assertEqual(caught.exception.code, code)
        health = self.request("/health")
        self.assertEqual(health["instance"], self.info["instance"])
        self.assertNotIn("token", health)

    def test_two_clients_and_invalid_tool(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            outputs = list(pool.map(lambda _: self.request("/call", payload={"name": "pcbai_status", "arguments": {}}),
                                    range(2)))
        self.assertEqual(outputs[0]["sessions"], outputs[1]["sessions"])
        output = self.request("/call", payload={"name": "unknown", "arguments": {}})
        self.assertFalse(output["ok"])

    def test_marker_transport_gate_and_real_mcp_read(self):
        status = self.request("/call", payload={"name": "pcbai_status", "arguments": {}})
        session = status["sessions"][0]
        target = dict(session=session["id"], document="Test.kicad_sch", revision=session["revision"])
        current = self.request("/call", payload={"name": "get_markers", "arguments": {"session": session["id"]}})
        args = dict(target, mode="preview", markers_revision=current["markers_revision"],
                    marker=dict(kind="point", space="sch", points_mm=[[10,20]], note="User annotation"))
        denied = self.request("/call", payload={"name": "set_marker", "arguments": args})
        self.assertEqual(denied["error"]["code"], "unknown_tool")
        preview = self.request("/view/call", payload={"name": "set_marker", "arguments": args})
        self.assertTrue(preview["ok"], preview)
        saved = self.request("/view/call", payload={"name": "set_marker", "arguments": dict(target, mode="apply",
            markers_revision=current["markers_revision"], candidate_id=preview["candidate_id"])})
        self.assertTrue(saved["ok"], saved)
        message = dict(jsonrpc="2.0", id=1, method="tools/call", params={"name": "get_markers", "arguments": {"session": session["id"]}})
        process = subprocess.run([sys.executable, "-m", "mcp_server.pcbai_mcp"], env=self.env,
            input=(json.dumps(message)+"\n").encode(), shell=False, capture_output=True, timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.assertEqual(process.returncode, 0, process.stderr)
        output = json.loads(process.stdout)["result"]["structuredContent"]
        self.assertEqual(output["markers"][0]["note"], "User annotation")
        self.assertTrue(output["markers"][0]["trusted"])

    def test_job_can_be_polled_over_a_new_connection(self):
        status = self.request("/call", payload={"name": "pcbai_status", "arguments": {}})
        session = status["sessions"][0]
        target = dict(session=session["id"], document="Test.kicad_pcb", revision=session["revision"])
        submitted = self.request("/call", payload={"name": "start_job", "arguments": dict(target, tool="board_stats")})
        self.assertTrue(submitted["ok"], submitted)
        identity = submitted["job"]["job_id"]
        # Each request uses a fresh connection; the submitting connection is closed.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            output = self.request("/call", payload={"name": "job_status", "arguments": {"job_id": identity}})
            if output["job"]["status"] in {"completed", "failed"}:
                break
            time.sleep(0.02)
        else:
            self.fail("Read-only background job did not finish")
        self.assertEqual(output["job"]["target"], target)
        self.assertIn("ok", output["job"]["result"])

    def test_singleton_rejects_duplicate_and_keeps_identity(self):
        duplicate = self.start([sys.executable, "-m", "pcbai", "serve", "--project", str(self.project)])
        _, stderr = duplicate.communicate(timeout=15)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn(b"already holds", stderr)
        duplicate.stdout.close()
        duplicate.stderr.close()
        self.assertEqual(self.request("/health")["instance"], self.info["instance"])

    def test_real_mcp_stdio_to_service(self):
        messages = [dict(jsonrpc="2.0", id=1, method="initialize", params={"protocolVersion": "2025-11-25"}),
                    dict(jsonrpc="2.0", id=2, method="tools/list"),
                    dict(jsonrpc="2.0", id=3, method="tools/call", params={"name": "pcbai_status", "arguments": {}})]
        process = subprocess.run([sys.executable, "-m", "mcp_server.pcbai_mcp"], env=self.env,
                                 input=b"\n".join(json.dumps(m).encode() for m in messages) + b"\n",
                                 capture_output=True, timeout=20,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.assertEqual(process.returncode, 0, process.stderr.decode())
        results = {r["id"]: r for r in map(json.loads, process.stdout.splitlines())}
        self.assertEqual(len(results), 3)
        self.assertGreater(len(results[2]["result"]["tools"]), 5)
        self.assertTrue(results[3]["result"]["structuredContent"]["ok"])
        self.assertEqual(process.stderr, b"")

    def test_client_recovers_from_dead_service_without_replaying_tool_call(self):
        self.stop()
        # Leave stale discovery metadata, as a crashed service does.
        (self.state / "service.json").write_text(json.dumps(self.info), encoding="utf-8")
        with patch.dict(os.environ, self.env):
            client = Client()
            try:
                tools = client.request("GET", "/tools")
                self.assertGreater(len(tools["tools"]), 5)
                replacement = client.info
                self.assertNotEqual(replacement["instance"], self.info["instance"])
                output = client.request("POST", "/call", {"name": "pcbai_status", "arguments": {}})
                self.assertTrue(output["ok"])
            finally:
                process = getattr(client, "started_process", None)
                if process is not None:
                    client.shutdown()
                    process.wait(timeout=10)

    def test_oversized_negative_body_and_unknown_payload_rejected(self):
        for headers, payload in [({"Content-Length": "-1"}, {}),
                                 ({"Content-Length": str(2 * 1024 * 1024)}, {}),
                                 ({}, {"name": "doctor", "arguments": {}, "extra": "no"})]:
            with self.subTest(headers=headers), self.assertRaises(HTTPError) as caught:
                self.request("/call", payload=payload, headers=headers)
            self.assertEqual(caught.exception.code, 400)
