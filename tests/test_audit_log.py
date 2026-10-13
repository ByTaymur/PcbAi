import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from pcbai.tools.engine import Engine
from pcbai.verify.audit import AuditLog
from tests.helpers import make_project


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        project = make_project(root / "project")
        self.state = root / "state"
        self.state.mkdir()
        self.engine = Engine([project], self.state)
        self.addCleanup(self.engine.jobs.close)

    def test_every_call_one_row_and_errors_logged_without_argument_values(self):
        self.engine.call("pcbai_status", {})
        self.engine.call("erc", dict(session="PRIVATE-TOKEN-NEVER-LOG", document="secret"))
        data = (self.state / "audit.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("PRIVATE-TOKEN", data)
        self.assertNotIn("secret", data)
        rows = [json.loads(row) for row in data.splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertFalse(rows[1]["ok"])

    def test_rotation_keeps_single_backup(self):
        log = AuditLog(self.state, limit=150)
        for i in range(5):
            log.append(dict(tool="test", ok=True, index=i))
        self.assertTrue((self.state / "audit.1.jsonl").is_file())
        self.assertTrue((self.state / "audit.jsonl").is_file())
        self.assertFalse((self.state / "audit.2.jsonl").exists())

    def test_audit_write_failure_does_not_break_tool(self):
        with patch.object(self.engine.audit, "append", side_effect=OSError("cannot write")):
            output = self.engine.call("pcbai_status", {})
        self.assertTrue(output["ok"])
        self.assertIn("audit_write_failed", output["warnings"][0])

    def test_concurrent_rows_are_not_corrupted(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda i: self.engine.call("pcbai_status", {}), range(30)))
        rows = (self.state / "audit.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rows), 30)
        self.assertTrue(all(json.loads(row)["ok"] for row in rows))

    def test_audit_reuses_validated_revision_without_extra_project_hash(self):
        from pcbai.kicad.files import revision
        session = next(iter(self.engine.sessions.entries.values()))
        with patch("pcbai.service.sessions.revision", wraps=revision) as hashed:
            self.engine._dispatch_call("list_symbols", dict(session=session.id, document="Test.kicad_sch"))
            intrinsic_scans = hashed.call_count
            hashed.reset_mock()
            output = self.engine.call("list_symbols", dict(session=session.id, document="Test.kicad_sch"))
        self.assertTrue(output["ok"], output)
        # Audit must add no scan beyond the tool's existing safety/context checks.
        self.assertGreaterEqual(intrinsic_scans, 2)
        self.assertEqual(hashed.call_count, intrinsic_scans)
        row = json.loads((self.state / "audit.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(row["revision_before"], output["target"]["revision"])
        self.assertEqual(row["revision_after"], row["revision_before"])

    def test_parallel_document_calls_keep_their_own_audit_target(self):
        session = next(iter(self.engine.sessions.entries.values()))
        cases = [("list_symbols", "Test.kicad_sch"), ("list_footprints", "Test.kicad_pcb")] * 5
        def call(case):
            tool, document = case
            return self.engine.call(tool, dict(session=session.id, document=document))
        with ThreadPoolExecutor(max_workers=2) as pool:
            outputs = list(pool.map(call, cases))
        self.assertTrue(all(o["ok"] for o in outputs))
        rows = [json.loads(line) for line in (self.state / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), len(cases))
        for row in rows:
            self.assertEqual(row["document"], "Test.kicad_sch" if row["tool"] == "list_symbols" else "Test.kicad_pcb")
            self.assertEqual(row["revision_before"], row["revision_after"])
