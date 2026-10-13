import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from pcbai.core.contract import PcbAiError
from pcbai.kicad.cli import rule_check, snapshot
from pcbai.kicad.files import revision
from tests.helpers import make_project


class CLIContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = make_project(Path(self.temp.name) / "project")

    def check_with_report(self, report, code=0, kind="erc"):
        def fake_run(argv, **_kwargs):
            output = Path(argv[argv.index("--output") + 1])
            output.write_text(json.dumps(report), encoding="utf-8")
            return CompletedProcess(argv, code, "", "")
        with patch("pcbai.kicad.cli.find_kicad_cli", return_value="kicad-cli"), patch("pcbai.kicad.cli.run", fake_run):
            return rule_check(self.project.parent, "Test.kicad_sch" if kind == "erc" else "Test.kicad_pcb", kind)

    def test_violation_exit_is_a_valid_finding_not_a_crash(self):
        output = self.check_with_report({"sheets": [{"path": "/", "violations": [{"severity": "error"}]}]}, 5)
        self.assertEqual(output["errors"], 1)
        self.assertFalse(output["clean"])

    def test_missing_report_sections_and_unknown_severity_fail_closed(self):
        for report in [{}, {"sheets": []}, {"sheets": [{"violations": [{"severity": "unknown"}]}]}]:
            with self.subTest(report=report), self.assertRaises(PcbAiError):
                self.check_with_report(report)

    def test_all_drc_groups_and_exclusions_are_counted(self):
        output = self.check_with_report({"violations": [{"severity": "warning"}],
                                         "unconnected_items": [{"severity": "error"}],
                                         "schematic_parity": [{"severity": "error", "excluded": True}]}, kind="drc")
        self.assertEqual(output["errors"], 1)
        self.assertEqual(output["warning_count"], 1)
        self.assertEqual(len(output["findings"]), 3)

    def test_snapshot_preserves_rules_and_project_local_library(self):
        library = self.project.parent / "pcbai/lib"
        library.mkdir(parents=True)
        (library / "parts.kicad_sym").write_text('(kicad_symbol_lib)')
        rules = self.project.with_suffix(".kicad_dru")
        rules.write_text('(version 1)')
        before = revision(self.project.parent)
        with snapshot(self.project.parent, before) as copy:
            self.assertEqual((copy / "pcbai/lib/parts.kicad_sym").read_bytes(),
                             (library / "parts.kicad_sym").read_bytes())
            self.assertTrue((copy / rules.name).is_file())
            self.assertEqual(revision(copy), before)

    def test_snapshot_rejects_stale_revision(self):
        with self.assertRaises(PcbAiError), snapshot(self.project.parent, "invented-revision"):
            pass
