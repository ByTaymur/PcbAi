import copy
import json
import math
import os
import tempfile
import unittest
from bisect import bisect_left
from pathlib import Path
from unittest.mock import patch

from pcbai.blocks.registry import describe, expand
from pcbai.core.contract import PcbAiError
from pcbai.ir.plan import plan, validate_ir
from pcbai.tools.engine import Engine
from pcbai.sim.runner import simulate_lines
from tests.test_parts import LIBRARY, FOOTPRINT
from tests.test_sim import kicad


def circuit():
    return dict(ir_version=1, requirements={"vin": "9-24 V", "board_mm": [40, 30], "layers": 2},
                rails={"GND": {"ground": True}}, blocks=[dict(id="DIV", block="voltage_divider",
                    params=dict(vin="12 V", r_top="10k", r_bottom="10k", r_load="20k"))],
                parts=[], connections=[["DIV.GND", "@GND"]])


class IrTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        symbols = self.root / "symbols"
        symbols.mkdir()
        (symbols / "Test.kicad_sym").write_bytes(LIBRARY)
        definitions = []
        for name in ("R", "C"):
            definitions.append(f'''(symbol "{name}" (property "Reference" "{name}") (property "Value" "{name}")
                (symbol "{name}_1_1" (pin passive line (at 0 0 0) (name "~") (number "1"))
                    (pin passive line (at 5 0 180) (name "~") (number "2"))))''')
        (symbols / "Device.kicad_sym").write_text('(kicad_symbol_lib (version 20231120) ' + " ".join(definitions) + ')')
        footprints = self.root / "footprints"
        for lib, name in (("Test", "Multi"), ("Resistor_SMD", "R_0603_1608Metric"),
                          ("Capacitor_SMD", "C_0603_1608Metric")):
            folder = footprints / (lib + ".pretty")
            folder.mkdir(parents=True)
            data = FOOTPRINT if lib == "Test" else b'(footprint "test" (pad "1" smd rect) (pad "2" smd rect))'
            (folder / (name + ".kicad_mod")).write_bytes(data)
        self.env = patch.dict(os.environ, PCBAI_SYMBOLS=str(symbols), PCBAI_FOOTPRINTS=str(footprints))
        self.env.start()
        self.addCleanup(self.env.stop)

    def fails(self, ir, code):
        with self.assertRaises(PcbAiError) as raised:
            plan(ir)
        self.assertEqual(raised.exception.code, code)

    def test_loaded_divider_literal_nets_and_unknown_acceptance(self):
        result = plan(circuit())
        self.assertEqual(result["requirements"]["vin"], dict(min=9, max=24, unit="V"))
        self.assertEqual(len(result["components"]), 3)
        out = next(n for n in result["nets"] if "DIV.OUT" in n["endpoints"])
        self.assertEqual(out["pins"], [dict(part="DIV/R1", pin="2"), dict(part="DIV/R2", pin="1"), dict(part="DIV/RL", pin="1")])
        self.assertAlmostEqual(result["calculations"][0]["outputs"]["vout"], 4.8)
        self.assertTrue(all(p["pin_pad_match"] for p in result["components"]))
        self.assertTrue(all(len(p["symbol_library_sha256"]) == 64 for p in result["components"]))
        self.assertFalse(result["ready_to_apply"])
        self.assertEqual(result["stages"]["electrical"], "incomplete")
        self.assertFalse(any(p["stock_verified"] or p["verified"] for p in result["components"]))

    def test_power_source_joins_rail_and_shorted_rails_fail(self):
        ir = circuit()
        ir["parts"] = [dict(id="U", symbol="Test:Base", footprint="Test:Multi")]
        ir["rails"]["VIN"] = {"from": "U.A1", "voltage": "12V", "current_limit": "300mA"}
        ir["connections"].append(["@VIN", "DIV.IN"])
        result = plan(ir)
        net = next(n for n in result["nets"] if n["rails"] == ["VIN"])
        self.assertIn("U.A1", net["endpoints"])
        self.assertEqual(result["rails"]["VIN"]["current_limit_a"], .3)
        ir["connections"].append(["U.A1", "@GND"])
        self.fails(ir, "rail_conflict")
        ir["connections"].pop()
        ir["rails"]["ALIAS"] = {"from": "U.A1"}
        self.fails(ir, "rail_conflict")
        del ir["rails"]["ALIAS"]
        ir["rails"]["VIN"]["from"] = "U.01"
        self.fails(ir, "invalid_rail_source")

    def test_literal_pin_identity_unknown_ports_and_global_ids(self):
        ir = circuit()
        ir["parts"] = [dict(id="U", symbol="Test:Base")]
        ir["connections"].append(["U.01", "DIV.OUT"])
        plan(ir)
        ir["connections"][-1][0] = "U.1"
        self.fails(ir, "unknown_endpoint")
        ir["connections"][-1][0] = "DIV.Unknown"
        self.fails(ir, "unknown_endpoint")
        ir["parts"][0]["id"] = "DIV"
        self.fails(ir, "duplicate_id")

    def test_closed_schema_suggestions_and_untrusted_claims(self):
        ir = circuit()
        ir["requirement"] = ir.pop("requirements")
        with self.assertRaises(PcbAiError) as raised:
            validate_ir(ir)
        findings = raised.exception.details
        self.assertTrue(any(f["suggestion"] == {"requirement": "requirements"} for f in findings))
        for update in ({"ir_version": True}, {"ir_version": 2}, {"$ref": "https://example.invalid/do-not-fetch"},
                       {"parts": [dict(id="R", symbol="Device:R", verified=True)]},
                       {"requirements": {"budget_usd": True}}, {"requirements": {"layers": 3}}):
            candidate = circuit() | update
            self.fails(candidate, "invalid_ir")

    def test_bounded_json_nonfinite_control_depth_and_expression(self):
        for value in (float("nan"), float("inf"), 10 ** 1000, "bad\u0001", b"data"):
            ir = circuit()
            ir["blocks"][0]["params"]["vin"] = value
            self.fails(ir, "invalid_ir")
        ir = circuit()
        node = ir["blocks"][0]["params"]
        for _ in range(20):
            node["nested"] = {}
            node = node["nested"]
        self.fails(ir, "invalid_ir")
        ir = circuit()
        ir["blocks"][0]["params"]["r_top"] = "__import__('os').system('bad')"
        self.fails(ir, "invalid_quantity")

    def test_constraints_variants_recipe_pin_guard_and_expansion_cap(self):
        ir = circuit()
        ir["constraints"] = [dict(edge="DIV.R1", side="left"), dict(around="DIV", keepout_mm=3)]
        self.assertTrue(plan(ir)["warnings"])
        ir["constraints"][0]["edge"] = "DIV.NO_SUCH_PART"
        self.fails(ir, "unknown_constraint_owner")
        ir = circuit()
        ir["blocks"] = [dict(id="B" + str(i), block="voltage_divider", params=dict(vin=12, r_top=10, r_bottom=10, r_load=20)) for i in range(51)]
        self.fails(ir, "circuit_too_large")
        ir = circuit()
        with patch("pcbai.ir.plan.expand", return_value=expand("voltage_divider", dict(vin=12, r_top=10, r_bottom=10)) | {
                "port_pins": {"OUT": [dict(part="R1", pin="01")]}}):
            self.fails(ir, "unknown_endpoint")
        for direction in ("pullup", "pulldown"):
            ir = circuit()
            ir["blocks"] = [dict(id="DIV", block="button_debounce", params=dict(r="10k", c="100nF", direction=direction))]
            result = plan(ir)
            net = next(n for n in result["nets"] if "DIV.OUT" in n["endpoints"])
            self.assertIn("DIV.INPUT", net["endpoints"])
            ports = expand("button_debounce", ir["blocks"][0]["params"])["ports"]
            self.assertEqual("SUPPLY" in ports, direction == "pullup")

    def test_local_library_change_and_pin_pad_mismatch_fail(self):
        ir = circuit()
        with patch("pcbai.ir.plan.verify_part", return_value=dict(pin_pad_match=True, symbol_library_sha256="changed")):
            self.fails(ir, "stale_library")
        file = self.root / "footprints/Resistor_SMD.pretty/R_0603_1608Metric.kicad_mod"
        file.write_bytes(b'(footprint "test" (pad "01" smd rect) (pad "2" smd rect))')
        self.fails(ir, "incompatible_pins")

    def test_tools_record_original_inputs_units_and_reproducible_report(self):
        engine = Engine([], self.root)
        args = dict(calculation="rc_filter", params=dict(r="10k", c="100nF"))
        calculated = engine.call("hand_calc", args)
        self.assertTrue(calculated["ok"], calculated)
        self.assertAlmostEqual(calculated["normalized_inputs"]["c"], 1e-7, places=18)
        evidence = json.loads((self.root / "evidence" / (calculated["evidence_id"] + ".json")).read_text())
        self.assertEqual(evidence["report"]["original_inputs"], args)
        self.assertEqual(evidence["measurements"][1]["unit"], "Hz")
        ir = circuit()
        source = copy.deepcopy(ir)
        planned = engine.call("plan_circuit", dict(ir=ir))
        self.assertTrue(planned["ok"], planned)
        self.assertEqual(ir, source)
        self.assertEqual(len(planned["ir_id"]), 64)
        self.assertTrue(all(b["maturity"] == 0 for b in engine.call("circuit_blocks", {})["blocks"]))
        for bad in (dict(calculation="rc_filter", params=dict(r=True, c="100nF")),
                    dict(calculation="rc_filter", params=dict(r="1k", c="1nF", file="bad")),
                    dict(calculation="rc_filter", params=dict(r=float("nan"), c="1nF"))):
            self.assertFalse(engine.call("hand_calc", bad)["ok"])
        self.assertEqual(describe()[0]["maturity"], 0)


@unittest.skipUnless(kicad(), "KiCad with shared ngspice required")
class BlockNgspiceTests(unittest.TestCase):
    def test_expanded_rc_values_match_cutoff_and_transient(self):
        block = expand("rc_filter", dict(r="10k", c="100nF"))
        values = {p["id"]: p["value_si"] for p in block["parts"]}
        expected = block["calculation"]["outputs"]
        tau, cutoff = expected["tau"], expected["cutoff"]
        with tempfile.TemporaryDirectory() as tmp:
            result = simulate_lines(["Expanded RC", "V1 in 0 PULSE(0 1 0 1n 1n 10m 20m)",
                f'R1 in out {values["R1"]:.12g}', f'C1 out 0 {values["C1"]:.12g}',
                f'.tran {tau / 1000:.12g} {tau * 5:.12g}', ".end"], tmp, ["time", "v(out)"])
            t, v = result["vectors"]["time"]["values"], result["vectors"]["v(out)"]["values"]
            for multiple in (.25, .5, 1, 2, 4):
                target = tau * multiple
                i = bisect_left(t, target)
                measured = v[i - 1] + (v[i] - v[i - 1]) * (target - t[i - 1]) / (t[i] - t[i - 1])
                self.assertLess(abs(measured / (1 - math.exp(-multiple)) - 1), .01)
            result = simulate_lines(["Expanded RC AC", "V1 in 0 AC 1", f'R1 in out {values["R1"]:.12g}',
                f'C1 out 0 {values["C1"]:.12g}', f'.ac lin 3 {cutoff / 2:.12g} {cutoff * 1.5:.12g}', ".end"], tmp, ["frequency", "v(out)"])
            voltage = result["vectors"]["v(out)"]["values"]
            measured = math.hypot(voltage["real"][1], voltage["imag"][1])
            self.assertLess(abs(measured * math.sqrt(2) - 1), .01)
