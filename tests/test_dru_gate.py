import shutil
import tempfile
import unittest
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli
from pcbai.kicad.dru import preflight, probe_rules
from pcbai.tools.engine import Engine


class PreflightTests(unittest.TestCase):
    def problems(self, text):
        return preflight(text.encode())["problems"]

    def test_valid_rules_and_comments_pass(self):
        checked = preflight(b'(version 1)\n# note\n(rule "HV" (constraint clearance (min 1.5mm))\n'
                            b'  (condition "A.NetClass == \'HV\'") (layer outer) (severity error))\n'
                            b'(rule "vias" (constraint via_count (max 2)))')
        self.assertEqual((checked["rules"], checked["problems"]), (2, []))
        self.assertEqual(preflight(b"  \n# only a comment\n"), dict(rules=0, problems=[]))

    def test_malformed_rules_are_named(self):
        cases = {
            '(version 1)\n(rule "a" (constraint clearance (min 0.2mm))': "not a complete S-expression",
            '(version 1)\n(rule "a" (constraint clearance (min 0.2)))': "has no unit",
            '(rule "a" (constraint clearance (min 1mm)))': "exactly one (version 1)",
            '(version 1)\n(rule "a" (constraint clearance (min 1mm)) (conditon "x"))': "unknown clause",
            '(version 1)\n(rule "a" (condition "A.Type == \'Pad\'"))': "no (constraint",
            '(version 1)\n(rule "a" (constraint clearance (min 1mm)) (condition "(A"))': "balanced",
            '(version 1)\n(rule "a" (constraint clearance (min 1mm)))\n(rule "a" (constraint clearance (min 2mm)))':
                "duplicate name",
            '(version 1)\n(rules "a")': "unknown top-level",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertTrue(any(expected in p for p in self.problems(text)), self.problems(text))

    def test_bounds_and_encoding(self):
        self.assertIn("4 MiB", preflight(b"#" * (4 * 1024 * 1024 + 1))["problems"][0])
        self.assertIn("UTF-8", preflight(b"(version 1)\xff")["problems"][0])

    def test_probe_keeps_original_rules_and_adds_one_named_rule(self):
        name, data = probe_rules(b'(version 1)\n(rule "a" (constraint clearance (min 1mm)))\n')
        checked = preflight(data)
        self.assertEqual((checked["rules"], checked["problems"]), (2, []))
        self.assertIn(name.encode(), data)
        self.assertNotEqual(name, probe_rules(b"")[0])
        self.assertEqual(preflight(probe_rules(b"")[1])["rules"], 1)


def ecc83():
    try:
        path = Path(find_kicad_cli()).parent.parent / "share/kicad/demos/ecc83"
    except PcbAiError:
        return None
    return path if path.is_dir() else None


@unittest.skipUnless(ecc83(), "Installed KiCad ecc83 demo required")
class RealKiCadGateTests(unittest.TestCase):
    """KiCad 10.0.x exits 0 when it drops a rules file; the gate must turn that into a failed DRC."""

    def drc(self, rules):
        with tempfile.TemporaryDirectory(prefix="pcbai-dru-gate-") as tmp:
            root = Path(tmp) / "p"
            shutil.copytree(ecc83(), root)
            state = Path(tmp) / "state"
            state.mkdir()
            project = next(root.glob("*.kicad_pro"))
            if rules is not None:
                project.with_suffix(".kicad_dru").write_bytes(rules)
            engine = Engine([project], state)
            session = next(iter(engine.sessions.entries.values()))
            response = engine.call("drc", session.target(project.with_suffix(".kicad_pcb").name))
            rows = {row["check_id"]: row for row in response.get("checks_run", [])}
            return response, rows

    def test_no_rules_file_is_not_applicable(self):
        response, rows = self.drc(None)
        self.assertTrue(response["ok"], response)
        self.assertEqual(rows["custom_rules"]["status"], "not_applicable")
        self.assertFalse(rows["custom_rules"]["required"])

    def test_loaded_rules_are_a_required_check_that_ran(self):
        response, rows = self.drc(b'(version 1)\n(rule "wide" (constraint clearance (min 0.3mm)))')
        self.assertTrue(response["ok"], response)
        self.assertEqual((rows["custom_rules"]["status"], rows["custom_rules"]["required"]), ("ran", True))
        self.assertFalse(any("pcbai_probe_" in str(f) for f in response.get("findings", [])))

    def test_malformed_file_fails_before_kicad(self):
        response, rows = self.drc(b'(version 1)\n(rule "broken" (constraint clearance (min 0.2mm))')
        self.assertEqual(response["error"]["code"], "custom_rules_invalid")
        self.assertEqual((rows["drc"]["status"], rows["drc"]["reason"]), ("failed", "custom_rules_invalid"))

    def test_file_kicad_cannot_compile_is_caught_by_the_probe(self):
        for rules in (b'(version 1)\n(rule "k" (constraint frobnicate (min 1mm)))',
                      b'(version 1)\n(rule "c" (constraint clearance (min 0.3mm)) (condition "A.Foo ==== 1"))'):
            with self.subTest(rules=rules):
                response, rows = self.drc(rules)
                self.assertEqual(response["error"]["code"], "custom_rules_not_loaded")
                self.assertEqual(rows["drc"]["status"], "failed")
