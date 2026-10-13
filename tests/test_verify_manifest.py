import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pcbai.core.contract import PcbAiError
from pcbai.tools.engine import Engine
from pcbai.verify.manifest import entry, verification
from tests.helpers import make_project


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.project = make_project(root / "project")
        state = root / "state"
        state.mkdir()
        self.engine = Engine([self.project], state)
        self.addCleanup(self.engine.jobs.close)
        self.session = next(iter(self.engine.sessions.entries.values()))

    def test_plain_drc_records_parity_not_requested(self):
        check = dict(errors=0, warning_count=0, findings=[], report={}, clean=True)
        with patch("pcbai.tools.engine.rule_check", return_value=check):
            output = self.engine.call("drc", self.session.target("Test.kicad_pcb"))
        row = output["checks_run"][1]
        self.assertEqual((row["check_id"], row["required"], row["status"], row["reason"]),
                         ("schematic_parity", False, "skipped", "not_requested"))
        self.assertIn("parite istenmedi", output["summary"])

    def test_excluded_finding_blocks_checks_ok(self):
        self.assertEqual(verification([entry("drc")], [dict(excluded=True)]), "checks_findings")
        self.assertEqual(verification([entry("drc", status="failed", reason="crash")], []), "checks_incomplete")
        self.assertEqual(verification([], []), "checks_incomplete")

    def test_one_check_crash_others_still_run(self):
        calls = []
        original = self.engine._call
        def run(name, args, session):
            if name != "check":
                calls.append((name, args.get("parity", False)))
                if name == "drc" and not args.get("parity"):
                    raise RuntimeError("injected crash")
                return dict(ok=True, findings=[], evidence_id="test")
            return original(name, args, session)
        with patch.object(self.engine, "_call", side_effect=run):
            output = self.engine.call("check", dict(session=self.session.id, scope="pcb"))
        self.assertEqual(output["verified"], "checks_incomplete")
        self.assertEqual(len(calls), 3)
        self.assertEqual([r["status"] for r in output["checks_run"]], ["failed", "ran", "ran"])

    def test_missing_pcb_is_skipped(self):
        self.project.with_suffix(".kicad_pcb").unlink()
        output = self.engine.call("check", dict(session=self.session.id, scope="pcb"))
        self.assertEqual(output["verified"], "checks_incomplete")
        self.assertTrue(all(r["reason"] == "document_missing" for r in output["checks_run"]))

    def test_fixture12_missing_cli_is_checks_incomplete(self):
        with patch.dict("os.environ", PCBAI_KICAD_CLI=str(self.project.parent / "absent-cli")):
            output = self.engine.call("check", dict(session=self.session.id, scope="sch"))
        self.assertEqual(output["verified"], "checks_incomplete")
        self.assertEqual(output["checks_run"][0]["reason"], "missing_dependency")

    def test_unknown_limit_id_rejected(self):
        with self.assertRaises(PcbAiError):
            entry("test", status="skipped", reason="unsupported", limit_id="not-real")

    def test_failed_parity_keeps_requested_coverage_and_input_hashes(self):
        with patch.dict("os.environ", PCBAI_KICAD_CLI=str(self.project.parent / "absent-cli")):
            output = self.engine.call("drc", dict(self.session.target("Test.kicad_pcb"), parity=True))
        self.assertEqual([r["check_id"] for r in output["checks_run"]], ["drc", "schematic_parity"])
        self.assertTrue(all(r["status"] == "failed" and r["inputs_sha256"] for r in output["checks_run"]))

    def test_required_not_applicable_cannot_certify(self):
        self.assertEqual(verification([entry("requested", status="not_applicable")], []), "checks_incomplete")

    def test_fixture01_scope_pcb_is_checks_findings(self):
        from tests.test_fault_fixtures import FaultFixtureTests
        case = FaultFixtureTests()
        case.setUp()
        with case.fixture("01-drc-zero-short") as (engine, session, _):
            output = engine.call("check", dict(session=session.id, scope="pcb"))
        self.assertEqual(output["verified"], "checks_findings", output)
        self.assertEqual([row["source"] for row in output["findings"]], ["parity"])
