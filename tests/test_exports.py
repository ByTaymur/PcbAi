import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from pcbai.core.contract import PcbAiError
from pcbai.kicad.exports import board_stats, render_board, stats_measurements
from pcbai.kicad.files import revision
from pcbai.tools.engine import Engine
from tests.helpers import make_project


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = make_project(self.root / "project")
        self.rev = revision(self.project.parent)
        (self.root / "state").mkdir()
        self.engine = Engine([self.project], self.root / "state")
        self.session = next(iter(self.engine.sessions.entries.values()))

    def test_stats_missing_or_invalid_values_cannot_be_certified(self):
        valid = dict(board=dict(has_outline=True, width="52.0700 mm", height="46.3550 mm"),
                     components=dict(total=dict(total=15)))
        self.assertEqual(stats_measurements(valid)[0]["value"], 52.07)
        for report in [{}, [], dict(valid, board=dict(has_outline=True, width="nan mm", height="1 mm")),
                       dict(valid, components=dict(total=dict(total=True)))]:
            with self.subTest(report=report), self.assertRaises(PcbAiError):
                stats_measurements(report)

    def test_stats_cli_failure_or_invalid_json_is_reported(self):
        def fake(argv, **_kwargs):
            Path(argv[argv.index("--output") + 1]).write_text("broken", encoding="utf-8")
            return CompletedProcess(argv, 0, "", "")
        with patch("pcbai.kicad.exports.find_kicad_cli", return_value="cli"), patch("pcbai.kicad.exports.run", fake):
            with self.assertRaises(PcbAiError) as caught:
                board_stats(self.project.parent, "Test.kicad_pcb", self.rev)
            self.assertEqual(caught.exception.code, "invalid_report")

    def test_render_reports_real_dimensions_and_rejects_non_png(self):
        destination = self.root / "board.png"

        def fake(argv, **_kwargs):
            destination.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"
                                    + (312).to_bytes(4, "big") + (224).to_bytes(4, "big"))
            return CompletedProcess(argv, 0, "", "")
        with patch("pcbai.kicad.exports.find_kicad_cli", return_value="cli"), patch("pcbai.kicad.exports.run", fake):
            output = render_board(self.project.parent, "Test.kicad_pcb", destination, self.rev, width=320, height=240)
            self.assertEqual(output, dict(width=312, height=224))
        with patch("pcbai.kicad.exports.find_kicad_cli", return_value="cli"), \
                patch("pcbai.kicad.exports.run", return_value=CompletedProcess([], 0, "", "")):
            destination.write_bytes(b"not a PNG")
            with self.assertRaises(PcbAiError):
                render_board(self.project.parent, "Test.kicad_pcb", destination, self.rev)

    def test_artifact_discarded_if_project_changes_during_export(self):
        def export(_root, _document, destination, **_kwargs):
            destination.write_bytes(b"%PDF mock")
            path = self.project.with_suffix(".kicad_pcb")
            path.write_bytes(path.read_bytes() + b"\n")
        with patch("pcbai.tools.engine.export_pdf", export):
            output = self.engine.call("schematic_pdf", dict(session=self.session.id, document="Test.kicad_sch"))
        self.assertEqual(output["error"]["code"], "stale_revision")
        self.assertEqual(list(self.engine.exports.iterdir()), [])
        self.assertEqual(list(self.engine.evidence.root.iterdir()), [])

    def test_export_parameters_and_wrong_document_are_rejected_before_cli(self):
        args = dict(session=self.session.id, document="Test.kicad_pcb")
        with patch("pcbai.tools.engine.render_board") as render:
            for extra in [dict(width=True), dict(width=0), dict(height=100000), dict(side=";evil"),
                          dict(executable="evil"), dict(document="Test.kicad_sch")]:
                self.assertFalse(self.engine.call("render_board", dict(args, **extra))["ok"])
            render.assert_not_called()

    def test_pdf_artifact_has_revision_bound_evidence(self):
        def export(_root, _document, destination, **_kwargs):
            destination.write_bytes(b"%PDF mock")
        with patch("pcbai.tools.engine.export_pdf", export):
            output = self.engine.call("schematic_pdf", dict(session=self.session.id, document="Test.kicad_sch"))
        self.assertTrue(output["ok"], output)
        evidence = json.loads((self.engine.evidence.root / (output["evidence_id"] + ".json")).read_text())
        self.assertEqual(evidence["target"]["revision"], self.rev)
        self.assertEqual(evidence["report"]["sha256"], output["sha256"])
