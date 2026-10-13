import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import Mock, patch

from pcbai.core.contract import PcbAiError
from pcbai.kicad.discover import discover, endpoints, inspect_board, request
from pcbai.kicad.ipc_worker import execute
from pcbai.tools.engine import Engine
from tests.helpers import PCB, make_project


class IPCTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.project = make_project(root / "project")
        (root / "state").mkdir()
        self.engine = Engine([self.project], root / "state")
        self.session = next(iter(self.engine.sessions.entries.values()))
        self.socket = "ipc://local-test-endpoint"
        environment = patch.dict(os.environ, PCBAI_KICAD_SOCKETS=json.dumps([self.socket]))
        environment.start()
        self.addCleanup(environment.stop)
        self.endpoint = next(iter(endpoints()))

    def test_configuration_and_tool_target_cannot_inject_endpoint_or_program(self):
        for value in ['"not a list"', "[]", '["tcp://remote:123"]', "broken"]:
            with patch.dict(os.environ, PCBAI_KICAD_SOCKETS=value), self.assertRaises(PcbAiError):
                endpoints()
        with patch("pcbai.kicad.discover.request") as transport:
            for endpoint in ["ipc://arbitrary-path", "ipc-" + "0" * 24]:
                with self.assertRaises(PcbAiError):
                    inspect_board(self.session, "Test.kicad_pcb", endpoint, "summary")
            transport.assert_not_called()
        args = dict(session=self.session.id, document="Test.kicad_pcb", endpoint_id=self.endpoint, executable="evil")
        self.assertEqual(self.engine.call("get_selection", args)["error"]["code"], "invalid_arguments")

    def test_discovery_only_matches_registered_document_and_discloses_probe_failure(self):
        records = [dict(project=str(self.project), document="Test.kicad_pcb"),
                   dict(project=str(self.project), document="../external.kicad_pcb"),
                   dict(project=str(self.project.parent / "Other.kicad_pro"), document="Test.kicad_pcb")]
        with patch("pcbai.kicad.discover.request", return_value=dict(ok=True, documents=records)):
            found = discover(self.engine.sessions)
        self.assertEqual(found["channels"][0]["registered_documents"],
                         [dict(session=self.session.id, document="Test.kicad_pcb")])
        with patch("pcbai.kicad.discover.request", side_effect=PcbAiError("timeout", "no response")):
            failed = discover(self.engine.sessions)
        self.assertEqual(failed["channels"], [])
        self.assertEqual(failed["unavailable"][0]["code"], "timeout")

    def test_worker_is_a_bounded_subprocess_with_json_data_on_stdin(self):
        with patch("pcbai.kicad.discover.run", return_value=CompletedProcess([], 0, '{"ok":true}', "")) as runner:
            request(self.socket, "discover")
        args, kwargs = runner.call_args
        self.assertEqual(args[0][1:], ["-m", "pcbai.kicad.ipc_worker"])
        self.assertEqual(kwargs["timeout"], 5)
        self.assertEqual(json.loads(kwargs["input_data"])["socket"], self.socket)
        with patch("pcbai.kicad.discover.run", return_value=CompletedProcess([], 0, "not json", "")), \
                self.assertRaises(PcbAiError):
            request(self.socket, "discover")

    def test_live_read_keeps_saved_and_live_revision_distinct_and_never_writes(self):
        args = dict(session=self.session.id, document="Test.kicad_pcb", endpoint_id=self.endpoint)
        before = self.project.with_suffix(".kicad_pcb").read_bytes()
        with patch("pcbai.tools.engine.inspect_board", return_value=dict(contents=PCB.decode() + "\n", selection=[])):
            response = self.engine.call("get_selection", args)
        self.assertTrue(response["ok"], response)
        self.assertFalse(response["buffer_matches_saved_bytes"])
        self.assertEqual(len(response["live_revision"]), 64)
        self.assertNotEqual(response["live_revision"], response["target"]["revision"])
        self.assertEqual(self.project.with_suffix(".kicad_pcb").read_bytes(), before)
        self.assertFalse(response["changed"])

    def worker_modules(self, documents):
        client = Mock()
        client.get_open_documents.return_value = documents
        kipy = types.ModuleType("kipy")
        kipy.KiCad = Mock(return_value=client)
        proto = types.ModuleType("kipy.proto.common.types")
        proto.DocumentType = types.SimpleNamespace(DOCTYPE_PCB=1)
        return {"kipy": kipy, "kipy.proto.common.types": proto}, client

    def test_worker_rejects_wrong_or_ambiguous_board_before_reading_buffer(self):
        document = types.SimpleNamespace(project=types.SimpleNamespace(path=str(self.project.parent), name="Other"),
                                         board_filename="Test.kicad_pcb")
        request_data = dict(socket=self.socket, operation="summary", project=str(self.project),
                            board=str(self.project.with_suffix(".kicad_pcb")))
        for documents in [[document], [document, document], []]:
            modules, client = self.worker_modules(documents)
            with patch.dict("sys.modules", modules), self.assertRaises(PcbAiError):
                execute(request_data)
            client.get_board.assert_not_called()

    def test_worker_detects_document_switch_after_live_read(self):
        document = types.SimpleNamespace(project=types.SimpleNamespace(path=str(self.project.parent), name="Test"),
                                         board_filename="Test.kicad_pcb")
        modules, client = self.worker_modules([document])
        client.get_board.return_value.document = document
        client.get_board.return_value.get_as_string.return_value = PCB.decode()
        # execute gets docs once, get_board is mocked (no additional lookup), then verifies docs again.
        client.get_open_documents.side_effect = [[document], []]
        with patch.dict("sys.modules", modules), self.assertRaises(PcbAiError) as caught:
            execute(dict(socket=self.socket, operation="summary", project=str(self.project),
                         board=str(self.project.with_suffix(".kicad_pcb"))))
        self.assertEqual(caught.exception.code, "wrong_target")
