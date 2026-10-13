import copy
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from pcbai.blocks.schematic import measure_topology, plan_block, reserve
from pcbai.core.contract import PcbAiError
from pcbai.kicad.cli import rule_check, snapshot
from pcbai.pcb.edit import Edits
from pcbai.sch.edit import hierarchy, plan_add_symbol
from pcbai.sch.scene import parse_netlist
from pcbai.sch_render import export_netlist
from pcbai.sexpr import Document
from pcbai.tools.engine import Engine
from tests import test_ir_plan
from tests.test_sch_authoring_integration import available


def args(block="voltage_divider", **extra):
    params = dict(vin="12V", r_top="10k", r_bottom="10k", r_load="20k")
    if block in {"rc_filter", "button_debounce"}:
        params = dict(r="10k", c="100nF")
    return dict(block=block, params=params, instance="DEMO", x_mm=25.4, y_mm=50.8) | extra


class BlockPlannerTests(unittest.TestCase):
    def setUp(self):
        test_ir_plan.IrTests.setUp(self)
        library = self.root / "symbols/Device.kicad_sym"
        library.write_bytes(library.read_bytes().replace(b'(at 5 0 180)', b'(at 5.08 0 180)'))
        self.data = ('(kicad_sch (version 20250114) (uuid "' + str(uuid.uuid4()) + '") (paper "A4") (lib_symbols))').encode()
        root_id = Document(self.data).root.child("uuid").value()
        self.context = dict(project="demo", root_uuid=root_id, sheet_path="/" + root_id, references=[])

    def fails(self, data, arguments, code):
        with self.assertRaises(PcbAiError) as raised:
            plan_block(data, arguments, self.context)
        self.assertEqual(raised.exception.code, code)

    def test_one_frozen_candidate_all_parts_unique_refs_and_topology(self):
        source = self.data
        self.context["references"] = [dict(reference="r01"), dict(reference="R003"), dict(reference="C1")]
        result = plan_block(source, args(), self.context)
        self.assertEqual(self.data, source)
        self.assertEqual(list(result["reference_map"].values()), ["R2", "R4", "R5"])
        self.assertEqual(len(result["symbol_uuids"]), 3)
        self.assertEqual(len(set(result["symbol_uuids"])), 3)
        self.assertEqual(len(result["expected_nets"]), 3)
        self.assertEqual(sorted(len(v) for v in result["expected_nets"].values()), [1, 2, 3])
        self.assertEqual(result["maturity"], 0)
        doc = Document(result["data"])
        self.assertEqual(len(doc.root.child("lib_symbols").all("symbol")), 1)

    def test_missing_unknown_bounds_grid_names_and_duplicate_namespace(self):
        for update, code in ((dict(instance="OUT[0]"), "invalid_arguments"), (dict(x_mm=25), "off_grid"),
                             (dict(y_mm=10.16), "layout_outside_page"), (dict(x_mm=250.19), "invalid_arguments"),
                             (dict(params={"vin": 12, "r_top": True, "r_bottom": 10}), "invalid_block_parameters")):
            self.fails(self.data, args() | update, code)
        for x in (203.2, 228.6):
            try:
                plan_block(self.data, args(x_mm=x), self.context)
            except PcbAiError as exc:
                self.assertIn(exc.code, {"invalid_arguments", "layout_outside_page"})
            else:
                self.fail("Whole layout escaped page")
        result = plan_block(self.data, args(), self.context)
        self.fails(result["data"], args(y_mm=101.6), "namespace_collision")
        self.context["references"] = [dict(reference=r) for r in result["affected_references"]]
        self.fails(result["data"], args(instance="OTHER"), "layout_collision")

    def test_cache_authority_compatibility_and_no_installed_rereads_during_build(self):
        result = plan_block(self.data, args(), self.context)
        # A graphic/property-only cache change remains authoritative at another clean origin.
        cached = result["data"].replace(b'(property "Value" "R")', b'(property "Value" "My resistor")', 1)
        self.context["references"] = [dict(reference=r) for r in result["affected_references"]]
        with patch("pcbai.sch.edit.installed_symbol", side_effect=AssertionError("unfrozen library read")):
            next_plan = plan_block(cached, args(instance="OTHER", y_mm=101.6), self.context)
        self.assertEqual(next_plan["library_inputs"]["Device:R"]["source"], "project_cache")
        self.assertIn(b'My resistor', next_plan["data"])
        for old, new in ((b'(pin passive', b'(pin power_out'), (b'(number "1")', b'(number "01")'),
                         (b'(at 0 0 0)', b'(at 1.27 0 0)'),
                         (b'(symbol "Device:R"', b'(symbol "Device:R" (power)'),
                         (b'(pin passive line', b'(pin passive line hide')):
            altered = cached.replace(old, new, 1)
            self.fails(altered, args(instance="OTHER", y_mm=101.6), "incompatible_cache")

    def test_debounce_aliases_highpass_and_frozen_library_revision(self):
        for direction in ("pullup", "pulldown"):
            result = plan_block(self.data, args("button_debounce", params=dict(r="10k", c="100nF", direction=direction)), self.context)
            self.assertEqual(result["port_nets"]["INPUT"], result["port_nets"]["OUT"])
            self.assertEqual("SUPPLY" in result["port_nets"], direction == "pullup")
        result = plan_block(self.data, args("rc_filter", params=dict(r="10k", c="100nF", type="highpass")), self.context)
        first = result["expected_nets"][result["port_nets"]["IN"]][0]
        self.assertEqual(first["reference"], result["reference_map"]["C1"])
        from pcbai.blocks import schematic
        original = schematic.symbol
        def changing(lib):
            info = original(lib)
            if lib == "Device:C":
                info["library_sha256"] = "changed"
            return info
        with patch("pcbai.blocks.schematic.symbol", side_effect=changing):
            self.fails(self.data, args("rc_filter"), "stale_library")

    def test_visible_fields_free_text_and_unsupported_layout_are_guarded(self):
        old = plan_add_symbol(self.data, dict(lib_id="Device:R", reference="R20", value="OLD",
            x_mm=25.4, y_mm=152.4), self.context)["data"]
        self.context["references"] = [dict(reference="R20")]
        edits = Edits(old)
        field = next(p for p in edits.doc.root.all("symbol")[0].all("property") if p.value() == "Reference").child("at")
        edits.atom(field.children[1], "25.4")
        edits.atom(field.children[2], "50.8")
        self.fails(edits.result(), args(), "layout_collision")
        for text_node in (b'(text "KEEP" (at 25.4 50.8 0) (effects (font (size 1.27 1.27))))',
                          b'(text "KEEP" (at 25.4 50.8 45) (effects (font (size 2 2)) (justify right)))'):
            self.fails(self.data[:-1] + text_node + b')', args(), "layout_collision")
        self.fails(self.data[:-1] + b'(text_box "KEEP" (start 20 20) (end 30 30)))', args(), "unsupported_layout")

    def test_exact_native_members_reject_missing_extra_and_shorted_nets(self):
        plan = {"expected_nets": {"A": [dict(reference="R1", pin="1")], "B": [dict(reference="R1", pin="2")]}}
        netlist = dict(pins={("R1", "1"): "/A", ("R1", "2"): "/B"},
                       members={"/A": [dict(reference="R1", pin="1")], "/B": [dict(reference="R1", pin="2")]})
        self.assertEqual(len(measure_topology(plan, netlist)), 2)
        for mode in ("missing", "extra", "short"):
            bad = copy.deepcopy(netlist)
            if mode == "missing":
                del bad["pins"]["R1", "1"]
            elif mode == "extra":
                bad["members"]["/A"].append(dict(reference="OLD", pin="1"))
            else:
                bad["pins"]["R1", "2"] = "/A"
                bad["members"]["/A"].append(dict(reference="R1", pin="2"))
            with self.assertRaises(PcbAiError) as raised:
                measure_topology(plan, bad)
            self.assertEqual(raised.exception.code, "connectivity_failed")
        refs = reserve([dict(id="R1", symbol="Device:R")], [dict(reference="R" + "0" * 5000 + "1")])
        self.assertEqual(refs, {"R1": "R2"})


@unittest.skipUnless(available(), "KiCad CLI/libraries required")
class BlockNativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pcbai-block-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        (self.root / "demo.kicad_pro").write_text("{}")
        self.path = self.root / "demo.kicad_sch"
        self.path.write_text('(kicad_sch (version 20250114) (generator "pcbai") '
            f'(uuid "{uuid.uuid4()}") (paper "A4") (lib_symbols) (embedded_fonts no))')
        state = Path(self.tmp.name) / "state"
        state.mkdir()
        self.engine = Engine([self.root / "demo.kicad_pro"], state)
        self.session = next(iter(self.engine.sessions.entries.values()))

    def test_all_recipe_variants_actual_native_member_sets(self):
        context = hierarchy(self.session, self.path.name)
        source = self.path.read_bytes()
        variants = [args(), args(params=dict(vin=12, r_top="10k", r_bottom="10k")),
                    args("rc_filter"), args("rc_filter", params=dict(r="10k", c="100nF", type="highpass")),
                    args("button_debounce", params=dict(r="10k", c="100nF", direction="pullup")),
                    args("button_debounce", params=dict(r="10k", c="100nF", direction="pulldown"))]
        for arguments in variants:
            with self.subTest(arguments=arguments):
                candidate = plan_block(source, arguments, context)
                check = rule_check(self.root, self.path.name, "erc", override=candidate["data"])
                self.assertEqual(check["errors"], 0, check)
                with snapshot(self.root) as copy:
                    (copy / self.path.name).write_bytes(candidate["data"])
                    native = parse_netlist(export_netlist(copy, self.path.name, copy / "block.xml"))
                measured = measure_topology(candidate, native)
                self.assertEqual(len(measured), len(candidate["expected_nets"]))
                self.assertEqual(len(native["components"]), len(candidate["symbol_uuids"]))
                self.assertEqual(self.path.read_bytes(), source)

    def test_one_preview_apply_checkpoint_restore_and_stale_candidate(self):
        source = self.path.read_bytes()
        target = self.session.target(self.path.name)
        preview = self.engine.call("add_block", dict(target, mode="preview", **args("rc_filter")))
        if not preview["ok"] and preview["error"]["code"] == "editor_open":
            self.skipTest("Close KiCad editors for real composite write lifecycle")
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(self.path.read_bytes(), source)
        self.assertEqual(len(preview["measured_nets"]), 3)
        self.assertTrue(preview["can_apply"])
        self.assertEqual(self.engine.history.list(self.session.id), [])
        bad = self.engine.call("add_block", dict(target, mode="apply", candidate_id=preview["candidate_id"], instance="DIFFERENT"))
        self.assertFalse(bad["ok"])
        changed = self.engine.call("add_block", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        self.assertTrue(changed["ok"], changed)
        self.assertIn(changed["verified"], {"erc_ok", "erc_findings"}, changed)
        self.assertEqual(changed["erc_after"]["errors"], 0, changed)
        self.assertEqual(len(self.engine.history.list(self.session.id)), 1)
        self.assertEqual(Document(self.path.read_bytes()).root.all("symbol")[0].child("uuid").value(), preview["symbol_uuids"][0])
        stale = self.engine.call("add_block", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        self.assertFalse(stale["ok"])
        new_target = self.session.target(self.path.name)
        restore = self.engine.call("restore_checkpoint", dict(new_target, mode="preview", checkpoint_id=changed["checkpoint"]["id"]))
        self.assertTrue(restore["ok"], restore)
        applied = self.engine.call("restore_checkpoint", dict(new_target, mode="apply", candidate_id=restore["candidate_id"]))
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(self.path.read_bytes(), source)

    def test_global_refs_reserved_before_byte_composition(self):
        context = hierarchy(self.session, self.path.name)
        old = plan_add_symbol(self.path.read_bytes(), dict(lib_id="Device:R", reference="R01", x_mm=25.4, y_mm=152.4), context)
        self.path.write_bytes(old["data"])
        context = hierarchy(self.session, self.path.name)
        candidate = plan_block(self.path.read_bytes(), args(), context)
        self.assertEqual(candidate["affected_references"], ["R2", "R3", "R4"])
