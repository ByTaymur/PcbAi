import io
import os
import json
import socket
import unittest
from unittest.mock import patch

from mcp_server import pcbai_mcp
from mcp_server.pcbai_mcp import META, handle, serve


class FakeClient:
    def request(self, method, path, payload=None):
        if path == "/tools":
            return {"tools": []}
        return {"ok": payload["name"] != "unknown", "changed": False}


class SlowEngineClient:
    """A 200 s engine preview: every single HTTP request returns quickly, the job finishes after `polls`."""
    def __init__(self, polls):
        self.polls, self.calls = polls, []

    def request(self, method, path, payload=None):
        name = payload["name"]
        self.calls.append(name)
        if name == "start_job":
            return {"ok": True, "job": {"job_id": "job-1", "status": "queued"}}
        if name == "job_status":
            self.polls -= 1
            if self.polls > 0:
                return {"ok": True, "job": {"job_id": "job-1", "status": "running"}}
            return {"ok": True, "job": {"job_id": "job-1", "status": "completed",
                                        "result": {"ok": True, "candidate_id": "c1", "changed": False}}}
        raise socket.timeout("timed out")


def tool_call(client, name, arguments):
    return handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": name, "arguments": arguments}}, client)["result"]["structuredContent"]


class MCPTests(unittest.TestCase):
    def test_long_engine_preview_runs_as_polled_job(self):
        client = SlowEngineClient(polls=3)
        with patch.object(pcbai_mcp, "POLL_SECONDS", 0):
            output = tool_call(client, "autoroute", {"session": "s", "document": "a.kicad_pcb", "revision": "r",
                                                     "mode": "preview", "engine": "tracemaker"})
        self.assertEqual(output["candidate_id"], "c1")
        self.assertEqual(client.calls, ["start_job", "job_status", "job_status", "job_status"])

    def test_unfinished_job_returns_job_id_instead_of_timeout(self):
        client = SlowEngineClient(polls=10 ** 6)
        with patch.object(pcbai_mcp, "POLL_SECONDS", 0), patch.dict(os.environ, {"PCBAI_MCP_JOB_WAIT": "0"}):
            output = tool_call(client, "autoplace", {"session": "s", "document": "a.kicad_pcb", "revision": "r",
                                                     "mode": "preview", "engine": "tracemaker"})
        self.assertTrue(output["ok"])
        self.assertEqual(output["status"], "running")
        self.assertEqual(output["job"]["job_id"], "job-1")

    def test_timed_out_apply_reports_unknown_change(self):
        output = tool_call(SlowEngineClient(polls=1), "autoroute", {"mode": "apply", "candidate_id": "c1"})
        self.assertFalse(output["ok"])
        self.assertIsNone(output["changed"])
        self.assertEqual(output["error"]["code"], "service_timeout")

    def test_initialize_and_modern_discovery(self):
        client = FakeClient()
        legacy = handle(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
            client,
        )
        self.assertEqual(legacy["result"]["protocolVersion"], "2025-11-25")
        modern = handle(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "server/discover",
                "params": {
                    "_meta": {META + "protocolVersion": "2026-07-28", META + "clientCapabilities": {}}
                },
            },
            client,
        )
        self.assertEqual(modern["result"]["resultType"], "complete")

    def test_invalid_requests_metadata_and_params(self):
        for msg, code in [
            (None, -32600),
            ({"jsonrpc": "2.0", "id": 1, "method": "x"}, -32601),
            ({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": []}, -32602),
            ({"jsonrpc": "2.0", "id": 1, "method": "server/discover"}, -32602),
        ]:
            with self.subTest(msg=msg):
                self.assertEqual(handle(msg, FakeClient())["error"]["code"], code)

    def test_notification_has_no_response(self):
        self.assertIsNone(handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, FakeClient()))

    def test_tool_error_and_structured_content(self):
        output = handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "unknown", "arguments": {}},
            },
            FakeClient(),
        )
        self.assertTrue(output["result"]["isError"])
        self.assertFalse(output["result"]["structuredContent"]["ok"])

    def test_marker_resource_prompt_and_explicit_target(self):
        from mcp_server.pcbai_mcp import dispatch, RpcError

        class Client:
            def request(self, _method, _path, payload):
                return (
                    {"ok": True, "sessions": [{"id": "s-target"}]}
                    if payload["name"] == "pcbai_status"
                    else {"ok": True, "markers": [{"n": 1, "trusted": False}]}
                )

        client = Client()
        listed = dispatch("resources/list", {}, client)
        self.assertIn("pcbai://markers", [r["uri"] for r in listed["resources"]])
        content = dispatch("resources/read", {"uri": "pcbai://markers"}, client)
        data = json.loads(content["contents"][0]["text"])
        self.assertFalse(data["sessions"][0]["markers"][0]["trusted"])
        prompt = dispatch(
            "prompts/get", {"name": "apply_markers", "arguments": {"session": "s-target"}}, client
        )
        self.assertIn("blocked", prompt["messages"][0]["content"]["text"])
        for args in [{}, {"session": "s-unknown"}]:
            with self.assertRaises(RpcError):
                dispatch("prompts/get", {"name": "apply_markers", "arguments": args}, client)

    def test_stdio_is_only_json_and_correlates_concurrent_ids(self):
        requests = [{"jsonrpc": "2.0", "id": i, "method": "ping"} for i in range(20)]
        source = io.BytesIO(b"bad json\n" + b"\n".join(json.dumps(r).encode() for r in requests))
        destination = io.BytesIO()
        serve(source, destination, FakeClient())
        outputs = [json.loads(line) for line in destination.getvalue().splitlines()]
        self.assertEqual(len(outputs), 21)
        self.assertEqual({o["id"] for o in outputs if "result" in o}, set(range(20)))
        self.assertEqual(outputs[0]["error"]["code"], -32700)

    def test_shared_service_may_hold_more_projects_but_not_fewer(self):
        from mcp_server.client import Client

        client = Client()
        a, b = os.path.abspath("A/A.kicad_pro"), os.path.abspath("B/B.kicad_pro")
        client.projects = [a]
        self.assertEqual(client.missing({"projects": [a, b]}), [])
        self.assertEqual(client.missing({"projects": [os.path.normcase(a)]}), [])
        client.projects = [a, b]
        self.assertEqual(client.missing({"projects": [a]}), [b])
        client.projects = []
        self.assertEqual(client.missing({"projects": []}), [])
