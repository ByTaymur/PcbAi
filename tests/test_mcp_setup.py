"""AJ-2: auto-approved tools come from readOnlyHint, and user-level MCP entries (no PCBAI_PROJECTS) never start a
service of their own."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mcp_server import client as client_module
from mcp_server.pcbai_mcp import handle
from mcp_server.readonly_tools import BUNDLED, bundled_text, read_only_tools, tool_definitions


class ReadOnlyToolsTests(unittest.TestCase):
    def test_bundled_copy_matches_registry(self):
        self.assertEqual(BUNDLED.read_text(encoding="utf-8"), bundled_text(),
                         "run python -m mcp_server.readonly_tools --write")

    def test_no_writing_tool_is_auto_approved(self):
        approved = set(read_only_tools())
        writers = {d["name"] for d in tool_definitions() if d["annotations"]["destructiveHint"]}
        self.assertTrue(writers)
        self.assertFalse(approved & writers)
        self.assertTrue({"set_value", "move_footprint", "checkpoint"} <= writers)
        self.assertIn("pcbai_status", approved)

    def test_missing_annotations_are_not_approved(self):
        self.assertEqual(read_only_tools([{"name": "x"}, {"name": "y", "annotations": {"readOnlyHint": False}}]), [])


class UserLevelClientTests(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.TemporaryDirectory()
        self.addCleanup(self.state.cleanup)
        env = {"PCBAI_STATE_DIR": self.state.name}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("PCBAI_PROJECTS", None)

    def test_no_projects_and_no_service_explains_instead_of_starting(self):
        client = client_module.Client()
        self.assertEqual(client.projects, [])
        with mock.patch.object(client_module.subprocess, "Popen") as popen:
            with self.assertRaises(client_module.ServiceUnavailable) as caught:
                client.connect()
        popen.assert_not_called()
        self.assertIn("PcbAi'ye kaydet", str(caught.exception))

    def test_no_projects_joins_running_service(self):
        Path(self.state.name, "service.json").write_text(json.dumps({"port": 1234, "token": "t" * 40, "instance": "i"}),
                                                         encoding="utf-8")
        client = client_module.Client()
        health = {"name": "pcbai", "instance": "i", "projects": ["C:/other/x.kicad_pro"]}
        with mock.patch.object(client, "_request", return_value=health), \
                mock.patch.object(client_module.subprocess, "Popen") as popen:
            client.connect()
        popen.assert_not_called()
        self.assertEqual(client.info["instance"], "i")

    def test_mcp_without_service_lists_status_and_returns_tool_error(self):
        client = client_module.Client()
        with mock.patch.object(client_module.subprocess, "Popen") as popen:
            listed = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, client)
            called = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                             "params": {"name": "pcbai_status", "arguments": {}}}, client)
        popen.assert_not_called()
        self.assertEqual([t["name"] for t in listed["result"]["tools"]], ["pcbai_status"])
        self.assertTrue(called["result"]["isError"])
        self.assertEqual(called["result"]["structuredContent"]["error"]["code"], "service_unavailable")


if __name__ == "__main__":
    unittest.main()
