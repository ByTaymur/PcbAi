import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pcbai.blocks.spice import bench
from pcbai.core.contract import PcbAiError
from pcbai.kicad.files import digest
from pcbai.sim.coverage import coverage, inventory
from pcbai.sim.runner import sanitize
from pcbai.tools.engine import Engine
from tests.helpers import make_project
from tests.test_blocks_spice import CASES
from tests.test_sim import kicad


def parts(*references):
    return [dict(reference=ref, active=ref.startswith("U"), connected=True, lib_id="") for ref in references]


XML = b'''<export><design><sheet number="1" name="/" tstamps=""><title_block><source>Test.kicad_sch</source></title_block></sheet></design>
<components><comp ref="R1"><value>1k</value><libsource lib="Device" part="R"/></comp>
<comp ref="U1"><libsource lib="Amplifier_Operational" part="OP"/></comp></components>
<nets><net name="N"><node ref="R1" pin="1"/><node ref="U1" pin="1"/></net></nets></export>'''


class ModelCoverageTests(unittest.TestCase):
    def test_all_passive_recipes_bind_without_fictitious_active_ratio(self):
        for block, params in CASES:
            recipe, lines, _ = bench(block, params)
            report = coverage(parts(*(p["id"] for p in recipe["parts"])), lines)
            self.assertEqual(report["ratio"], 1.0, report)
            self.assertEqual(report["unbound"], [])
            self.assertIsNone(report["active_ratio"])
            self.assertTrue(report["no_active_devices"])

    def test_omitted_opamp_remains_unbound_and_in_denominator(self):
        report = coverage(inventory(XML), ["Circuit", "R1 N 0 1k", ".end"])
        self.assertEqual(report["bound"], ["R1"])
        self.assertEqual(report["unbound"], ["U1"])
        self.assertEqual(report["ratio"], .5)
        self.assertEqual(report["active_ratio"], 0)
        self.assertTrue(report["bindings"][1]["connected"])

    def test_subcircuit_inner_devices_are_not_physical_references(self):
        lines = ["Circuit", ".subckt AMP a b", "R1 a b 10k", ".ends AMP", "XU1 N 0 AMP", "R1 N 0 1k"]
        report = coverage(parts("U1", "R1"), lines)
        self.assertEqual(report["bound"], ["R1", "U1"])
        self.assertEqual(len(report["bindings"]), 2)
        self.assertEqual(report["active_ratio"], 1)
        self.assertFalse(report["pins_verified"])

    def test_missing_model_wrong_arity_type_and_conditional_are_unbound(self):
        cases = [(["Circuit", "XU1 a b MISSING"], "missing_subcircuit"),
                 (["Circuit", ".subckt OP a b c", "R1 a b 1k", ".ends", "XU1 a b OP"], "model_pin_count_mismatch"),
                 (["Circuit", ".model MD NPN", "DU1 a b MD"], "model_type_mismatch"),
                 (["Circuit", ".if 1", "RU1 a b 1k", ".endif"], "conditional_netlist")]
        for lines, reason in cases:
            report = coverage(parts("U1"), lines)
            self.assertEqual(report["unbound"], ["U1"], report)
            self.assertEqual(report["bindings"][0]["reason"], reason)

    def test_model_scopes_case_and_extra_devices(self):
        lines = ["Circuit", ".model D0 D", ".subckt AMP a b", ".model D0 D", "d1 a b d0",
                 ".ends amp", "XU1 N 0 aMp", "VDRIVE N 0 5"]
        report = coverage(parts("U1"), lines)
        self.assertEqual(report["bound"], ["U1"])
        self.assertEqual(report["unmatched_spice_instances"], ["VDRIVE"])

    def test_duplicate_refs_models_instances_and_ambiguous_mapping_fail(self):
        cases = [(parts("U1", "u1"), ["Circuit"]),
                 (parts("U1"), ["Circuit", ".model D0 D", ".model d0 D"]),
                 (parts("R1"), ["Circuit", "R1 a b 1k", "r1 a b 1k"]),
                 (parts("U1", "XU1"), ["Circuit", "XU1 a b AMP"]),
                 (parts("U1"), ["Circuit", ".subckt AMP a b", ".subckt OTHER a b"])]
        for physical, lines in cases:
            with self.subTest(lines=lines), self.assertRaises(PcbAiError):
                coverage(physical, lines)
        with self.assertRaises(PcbAiError):
            inventory(XML.replace(b'<comp ref="U1">', b'<comp ref="R1">'))

    def test_static_no_analysis_supported_worker_sanitizer_keeps_analysis_gate(self):
        text = "Circuit\nR1 a 0 1k\n.end"
        self.assertEqual(sanitize(text, [], require_analysis=False)[2], [])
        with self.assertRaises(PcbAiError):
            sanitize(text, [])

    def test_empty_denominator_is_unknown_not_perfect(self):
        report = coverage([], ["Circuit", "R1 a b 1k"])
        self.assertIsNone(report["ratio"])
        self.assertEqual(report["unmatched_spice_instances"], ["R1"])

    def test_conditional_tabs_and_inline_comments_are_never_binding_evidence(self):
        for directive in (".if\t(0)", ".IF (0)", ".elseif\t(1)", ".else\t$ comment"):
            text = "\n".join(["* title", directive, "R1 1 0 1k", ".endif\t$ comment", ".end"])
            lines, _, _ = sanitize(text, [], require_analysis=False)
            report = coverage(parts("R1"), lines)
            self.assertEqual(report["unbound"], ["R1"])
            self.assertEqual(report["bindings"][0]["reason"], "conditional_netlist")

    def test_recursive_and_reused_subcircuits_resolve_with_bounded_depth(self):
        recursive = ["Circuit", ".subckt LOOP a b", "X1 a b LOOP", ".ends", "XU1 a b LOOP"]
        self.assertEqual(coverage(parts("U1"), recursive)["unbound"], ["U1"])
        lines = ["Circuit", ".subckt LEAF a b", "R1 a b 1k", ".ends"]
        for index in range(10):
            name = f"S{index}"
            previous = f"S{index - 1}" if index else "LEAF"
            lines.extend([f".subckt {name} a b", *[f"X{n} a b {previous}" for n in range(10)], ".ends"])
        lines.append("XU1 a b S9")
        self.assertEqual(coverage(parts("U1"), lines)["bound"], ["U1"])

    def test_end_terminates_deck_and_first_line_is_title(self):
        for text in ("Circuit\n.end\nR1 a b 1k", "Circuit\nD1 a b DM\n.end\n.model DM D",
                     "Circuit\n.subckt OP a b\n.end\n.ends\nXU1 a b OP"):
            lines, _, _ = sanitize(text, [], require_analysis=False)
            with self.assertRaises(PcbAiError):
                coverage(parts("R1", "D1", "U1"), lines)
        report = coverage(parts("D1"), [".model DM D", "D1 a b DM", ".end"])
        self.assertEqual(report["unbound"], ["D1"])


class CoverageEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        project = make_project(root / "project")
        state = root / "state"
        state.mkdir()
        self.engine = Engine([project], state)
        self.addCleanup(self.engine.jobs.close)
        self.session = next(iter(self.engine.sessions.entries.values()))
        self.target = self.session.target("Test.kicad_sch")

    def call(self, name, **extra):
        with patch("pcbai.tools.engine.export_spice", return_value="Circuit\nR1 N 0 1k\n.op\n.end"), \
                patch("pcbai.tools.engine.export_netlist", return_value=XML):
            return self.engine.call(name, dict(self.target, **extra))

    def test_threshold_blocks_worker_and_evidence_contains_coverage(self):
        with patch("pcbai.tools.engine.simulate_lines") as worker:
            output = self.call("simulate", min_coverage=1)
        worker.assert_not_called()
        self.assertEqual(output["verified"], "checks_incomplete", output)
        self.assertEqual(output["coverage"]["unbound"], ["U1"])
        entry = json.loads((self.engine.evidence.root / (output["evidence_id"] + ".json")).read_text())
        self.assertEqual(entry["report"]["native_netlist_sha256"], digest(XML))

    def test_static_read_and_threshold_schema_are_explicit(self):
        output = self.call("model_coverage", min_coverage=.5)
        self.assertEqual(output["verified"], "model_coverage_inspected", output)
        for minimum in (-.1, 1.1, True, float("nan")):
            bad = self.engine.call("model_coverage", dict(self.target, min_coverage=minimum))
            self.assertFalse(bad["ok"])

    def test_worker_failure_keeps_coverage_without_a_success_claim(self):
        with patch("pcbai.tools.engine.simulate_lines", side_effect=PcbAiError("simulation_failed", "fixture")):
            output = self.call("simulate")
        self.assertFalse(output["ok"])
        self.assertEqual(output["error"]["code"], "simulation_failed")
        self.assertEqual(output["coverage"]["unbound"], ["U1"])
        self.assertTrue(output["evidence_id"])

    def test_nested_same_basename_is_not_the_registered_root(self):
        make_project(self.session.root / "nested")
        output = self.engine.call("model_coverage", self.session.target("nested/Test.kicad_sch"))
        self.assertFalse(output["ok"])
        self.assertEqual(output["error"]["code"], "invalid_document")


@unittest.skipUnless(kicad(), "KiCad with shared ngspice required")
class RealCoverageTests(unittest.TestCase):
    def test_native_sallen_key_binding_and_excluded_opamp_gate(self):
        from pcbai.sexpr import Document
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sk"
            shutil.copytree(kicad() / "share/kicad/demos/simulation/sallen_key", root)
            state = Path(tmp) / "state"
            state.mkdir()
            engine = Engine([root / "sallen_key.kicad_pro"], state)
            self.addCleanup(engine.jobs.close)
            session = next(iter(engine.sessions.entries.values()))
            target = session.target("sallen_key.kicad_sch")
            before = (root / target["document"]).read_bytes()
            output = engine.call("model_coverage", dict(target, min_coverage=1))
            self.assertEqual(output["coverage"]["ratio"], 1, output)
            self.assertIn("U1", output["coverage"]["active_bound"])
            self.assertEqual((root / target["document"]).read_bytes(), before)
            doc = Document(before)
            opamp = next(n for n in doc.root.all("symbol") if any(p.value() == "Reference" and p.value(2) == "U1" for p in n.all("property")))
            node = opamp.child("exclude_from_sim").children[1]
            changed = before[:node.start] + b"yes" + before[node.end:]
            (root / target["document"]).write_bytes(changed)
            with patch("pcbai.tools.engine.simulate_lines") as worker:
                output = engine.call("simulate", dict(session.target(target["document"]), min_coverage=1))
            self.assertEqual(output["verified"], "checks_incomplete", output)
            self.assertIn("U1", output["coverage"]["unbound"])
            worker.assert_not_called()
