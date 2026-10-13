import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from pcbai.external import run
from tests.test_kicad_integration import demo_root


class CheckCLITests(unittest.TestCase):
    def test_json_non_utf8_stdout_preserves_unicode_and_all_exit_codes(self):
        for verified, code in (("checks_ok", 0), ("checks_findings", 1), ("checks_incomplete", 2)):
            with self.subTest(verified=verified):
                payload = dict(ok=True, verified=verified, summary="Türkçe açıklama: bağlantı yanlış — Ω",
                               findings=[dict(description="İşaret, şönt, ölçüm")])
                # Test the real process/serialization boundary with deterministic tool data.
                script = (
                    "import sys,json; from unittest.mock import patch, MagicMock; from pathlib import Path; "
                    "from pcbai.__main__ import main; "
                    "sys.argv=['pcbai','check','owned.kicad_pro','--json']; "
                    "session=MagicMock(); session.entries={'s':MagicMock(root=Path('.'))}; "
                    "engine=MagicMock(); engine.sessions.entries={'s':None}; "
                    f"engine.call.return_value=json.loads({json.dumps(json.dumps(payload))}); "
                    "\nwith patch('pcbai.service.sessions.Sessions',return_value=session), "
                    "patch('pcbai.tools.engine.Engine',return_value=engine), "
                    "patch('pcbai.config.state_directory',return_value=Path('.')):\n sys.exit(main())"
                )
                output = run([sys.executable, "-c", script],
                             env=dict(os.environ, PYTHONIOENCODING="cp1252:strict"), timeout=60)
                self.assertEqual(output.returncode, code, output.stderr)
                self.assertEqual(output.stderr, "")
                self.assertTrue(output.stdout.isascii())
                self.assertEqual(json.loads(output.stdout), payload)

    def run_fixture(self, slug, scope, *, missing=False, bad=False):
        if not bad and not missing and demo_root() is None:
            self.skipTest("Real KiCad CLI required")
        source = Path(__file__).parent / "fixtures/faults" / slug
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(source, root / "project")
            env = dict(os.environ, PCBAI_STATE_DIR=str(root / "state"))
            if missing:
                env["PCBAI_KICAD_CLI"] = str(root / "absent-cli")
            project = root / "project" / ("absent.kicad_pro" if bad else "fault.kicad_pro")
            return run([sys.executable, "-m", "pcbai", "check", project, "--scope", scope, "--json"],
                       env=env, timeout=120)

    def test_exit0_clean_sch(self):
        output = self.run_fixture("12-missing-required-tool", "sch")
        self.assertEqual(output.returncode, 0, output.stdout + output.stderr)

    def test_exit1_findings(self):
        output = self.run_fixture("01-drc-zero-short", "pcb")
        self.assertEqual(output.returncode, 1, output.stdout + output.stderr)

    def test_exit2_missing_tool(self):
        output = self.run_fixture("12-missing-required-tool", "sch", missing=True)
        self.assertEqual(output.returncode, 2, output.stdout + output.stderr)
        self.assertEqual(json.loads(output.stdout)["verified"], "checks_incomplete")

    def test_exit2_bad_project_path(self):
        self.assertEqual(self.run_fixture("12-missing-required-tool", "sch", bad=True).returncode, 2)

    def test_json_output_parses(self):
        output = self.run_fixture("12-missing-required-tool", "sch")
        self.assertEqual(json.loads(output.stdout)["verified"], "checks_ok")
