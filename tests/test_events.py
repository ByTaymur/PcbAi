import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from mcp_server.pcbai_mcp import META, handle
from pcbai.service.events import Events, client_name, guidance
from pcbai.tools.engine import Engine
from tests.helpers import make_project


class EventLogTests(unittest.TestCase):
    def test_client_names_are_normalized_data(self):
        self.assertEqual(client_name("vscode"), "vscode")
        self.assertEqual(client_name("KiCad"), "kicad")
        self.assertEqual(client_name(""), "builtin")
        self.assertEqual(client_name(None), "builtin")
        self.assertEqual(client_name("mcp:Claude Code"), "mcp:claude-code")
        hostile = "mcp:" + chr(252) + "n" + chr(239) + chr(13) + chr(10) + "X-Evil: 1"
        self.assertEqual(client_name(hostile), "mcp:n-x-evil-1")
        self.assertLessEqual(len(client_name("mcp:" + "a" * 500)), 44)

    def test_bounded_and_since(self):
        clock = iter(range(1000, 2000)).__next__
        events = Events(clock=clock, limit=500)
        for _ in range(600):
            events.record("vscode", "pcbai_status", {"ok": True})
        self.assertEqual(len(events.items), 500)
        last = events.recent(limit=50)
        self.assertEqual(len(last), 50)
        self.assertEqual(last[-1]["seq"], 600)
        self.assertEqual([e["seq"] for e in events.recent(since=598)], [599, 600])

    def test_event_visible_within_two_seconds(self):
        now = [100.0]
        events = Events(clock=lambda: now[0])
        seen = events.recent()
        events.record("mcp:claude-code", "set_value", {"ok": True, "change_id": "c1"})
        now[0] += 0.5  # next poll of the window
        fresh = events.recent(since=seen[-1]["seq"] if seen else None)
        self.assertEqual(len(fresh), 1)
        self.assertLessEqual(now[0] - fresh[0]["time"], 2)

    def test_guidance(self):
        self.assertIn("PCB editörünü kapatın", guidance({"outcome": "blocked"}))
        self.assertIn("Dosya → Geri al", guidance({"outcome": "ok", "change_id": "c1"}))
        self.assertIn("Yeniden yükle", guidance({"outcome": "ok", "change_id": "c1"}, can_revert=True))
        self.assertIsNone(guidance({"outcome": "ok", "change_id": None}))


class EngineEventTests(unittest.TestCase):
    def setUp(self):
        process_list = patch("pcbai.kicad.files.run", return_value=CompletedProcess([], 0, "", ""))
        process_list.start()
        self.addCleanup(process_list.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.project = make_project(root / "project")
        (root / "state").mkdir()
        self.engine = Engine([self.project], root / "state")
        session = next(iter(self.engine.sessions.entries))
        self.base = self.engine.sessions.get(session).target("Test.kicad_sch")

    def preview(self, client):
        return self.engine.call("set_value", dict(self.base, mode="preview", reference="R1",
                                                  value="SECRET-4k7"), client=client)

    def test_arguments_never_logged_and_client_kept(self):
        self.preview("mcp:Claude Code")
        self.engine.call("no_such_tool", {"note": "SECRET-arg"}, client="vscode")
        events = self.engine.recent_events()
        self.assertNotIn("SECRET", json.dumps(events))
        self.assertEqual([(e["client"], e["tool"]) for e in events],
                         [("mcp:claude-code", "set_value"), ("vscode", "<unknown>")])
        self.assertEqual(events[0]["outcome"], "ok")
        self.assertTrue(events[1]["outcome"].startswith("error:"))
        self.assertEqual(set(events[0]), {"seq", "time", "client", "tool", "outcome", "change_id"})

    def test_open_editor_is_blocked(self):
        (self.project.parent / "~Test.kicad_sch.lck").write_text("", encoding="utf-8")
        self.assertEqual(self.preview("kicad")["error"]["code"], "editor_open")
        event = self.engine.recent_events()[-1]
        self.assertEqual((event["client"], event["outcome"]), ("kicad", "blocked"))
        self.assertIn("Devam", guidance(event))


class McpClientInfoTests(unittest.TestCase):
    class Client:
        client_name = ""

        def request(self, method, path, payload=None):
            return {"tools": []}

    def test_legacy_initialize_records_client_info(self):
        client = self.Client()
        handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "clientInfo": {"name": "claude-code", "version": "2"}}}, client)
        self.assertEqual(client.client_name, "mcp:claude-code")

    def test_modern_meta_records_client_info(self):
        client = self.Client()
        handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": {
            META + "protocolVersion": "2026-07-28", META + "clientCapabilities": {},
            META + "clientInfo": {"name": "Codex"}}}}, client)
        self.assertEqual(client.client_name, "mcp:codex")


if __name__ == "__main__":
    unittest.main()
