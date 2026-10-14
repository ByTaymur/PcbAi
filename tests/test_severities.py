import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import run
from pcbai.kicad.cli import rule_check
from pcbai.verify.severities import ignored_rules
from tests import test_fault_fixtures
from tests.test_kicad_integration import demo_root


class SeverityReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pro = self.root / "test.kicad_pro"

    def settings(self, value):
        self.pro.write_text(json.dumps(value), encoding="utf-8")

    def test_union_unknown_required_optional_visible_and_scope_separated(self):
        self.settings(dict(board=dict(design_settings=dict(rule_severities=dict(clearance="ignore"))),
                           erc=dict(rule_severities=dict(pin_not_connected="ignore"))))
        rows = ignored_rules(self.root, "test.kicad_pcb", "drc", dict(ignored_checks=[
            dict(key="clearance"), dict(key="future_rule"), dict(key="missing_courtyard")]))
        by_rule = {r["rule"]: r for r in rows}
        self.assertEqual(by_rule["clearance"]["sources"], ["native", "project"])
        self.assertTrue(by_rule["future_rule"]["required"])
        self.assertFalse(by_rule["missing_courtyard"]["required"])
        self.assertNotIn("pin_not_connected", by_rule)
        self.assertEqual(ignored_rules(self.root, "test.kicad_sch", "erc", dict(ignored_checks=[]))[0]["rule"],
                         "pin_not_connected")

    def test_no_config_default_native_and_parity_scope(self):
        native = dict(ignored_checks=[dict(key="schematic_parity"), dict(key="single_global_label")])
        rows = ignored_rules(self.root, "test.kicad_pcb", "drc", native)
        self.assertFalse(next(r for r in rows if r["rule"] == "schematic_parity")["required"])
        rows = ignored_rules(self.root, "test.kicad_pcb", "drc", native, parity=True)
        self.assertTrue(next(r for r in rows if r["rule"] == "schematic_parity")["required"])

    def test_malformed_settings_cannot_look_clean(self):
        for text in ('{', '{"board":null}', '{"board":{"design_settings":{"rule_severities":{"x":null}}}}',
                     '{"erc":{},"erc":{}}', '{"other":NaN}'):
            with self.subTest(text=text):
                self.pro.write_text(text, encoding="utf-8")
                with self.assertRaises(PcbAiError):
                    ignored_rules(self.root, "test.kicad_pcb", "drc", {})

    def test_malformed_native_identity_rejected(self):
        with self.assertRaises(PcbAiError):
            ignored_rules(self.root, "test.kicad_pcb", "drc", {})
        for value in (None, {}, ["clearance"], [dict(key=None)]):
            with self.subTest(value=value), self.assertRaises(PcbAiError):
                ignored_rules(self.root, "test.kicad_pcb", "drc", dict(ignored_checks=value))

    def test_project_escape_rejected(self):
        with self.assertRaises(PcbAiError):
            ignored_rules(self.root, "../test.kicad_pcb", "drc", {})


@unittest.skipUnless(demo_root(), "Real KiCad CLI required")
class IgnoredRuleIntegrationTests(unittest.TestCase):
    def test_enabled_and_ignored_erc_drc_with_unchanged_revision(self):
        case = test_fault_fixtures.FaultFixtureTests()
        case.setUp()
        with case.fixture("17-ignored-required-rule") as (engine, session, project):
            from pcbai.kicad.files import revision
            before = revision(project)
            for kind, rule in (("erc", "pin_not_connected"), ("drc", "clearance")):
                document = "fault.kicad_sch" if kind == "erc" else "fault.kicad_pcb"
                ignored = engine.call(kind, session.target(document))
                self.assertEqual(ignored["verified"], "checks_incomplete", ignored)
                row = next(r for r in ignored["checks_run"] if r.get("rule") == rule)
                self.assertEqual((row["required"], row["status"], row["reason"]),
                                 (True, "skipped", "rule_ignored_in_project"))
                settings = json.loads((project / "fault.kicad_pro").read_text())
                section = settings["erc"] if kind == "erc" else settings["board"]["design_settings"]
                section["rule_severities"][rule] = "error"
                # Override only the copied project settings, never the registered source.
                enabled = rule_check(project, document, kind, override=json.dumps(settings).encode(),
                                     override_document="fault.kicad_pro", expected_revision=before)
                from pcbai.kicad.files import digest
                self.assertEqual(enabled["inputs_sha256"]["fault.kicad_pro"], digest(json.dumps(settings).encode()))
                self.assertGreater(sum(f["rule_id"] == rule for f in enabled["findings"]), 0, enabled)
                self.assertFalse(any(r["rule"] == rule for r in enabled["ignored_rules"]))
            output = engine.call("check", dict(session=session.id, scope="all"))
            self.assertEqual(output["verified"], "checks_incomplete", output)
            self.assertEqual(sum(r.get("rule") == "clearance" for r in output["checks_run"]), 1)
            self.assertTrue(output["warnings"])
            self.assertEqual(revision(project), before)

    def test_real_cli_exit2_for_each_scope(self):
        source = Path(__file__).parent / "fixtures/faults/17-ignored-required-rule"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(source, root / "project")
            for scope in ("sch", "pcb", "all"):
                output = run([sys.executable, "-m", "pcbai", "check", root / "project/fault.kicad_pro",
                              "--scope", scope, "--json"], timeout=120,
                             env=dict(os.environ, PCBAI_STATE_DIR=str(root / "state")))
                self.assertEqual(output.returncode, 2, output.stdout + output.stderr)
                self.assertEqual(json.loads(output.stdout)["verified"], "checks_incomplete")
