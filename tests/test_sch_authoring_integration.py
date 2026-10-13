"""Actual KiCad authoring measurements use newly owned projects, never user cards."""
import tempfile
import unittest
import uuid
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli
from pcbai.kicad.cli import snapshot
from pcbai.sch.scene import parse_netlist
from pcbai.sch_render import export_netlist
from pcbai.tools.engine import Engine


def available():
    try:
        return bool(find_kicad_cli())
    except PcbAiError:
        return False


@unittest.skipUnless(available(), "Installed KiCad CLI/libraries required")
class SchAuthoringIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pcbai-authoring-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        (self.root / "demo.kicad_pro").write_text("{}", encoding="utf-8")
        self.sheet = self.root / "demo.kicad_sch"
        self.sheet.write_text('(kicad_sch (version 20250114) (generator "pcbai") '
                             f'(uuid "{uuid.uuid4()}") (paper "A4") (lib_symbols) (embedded_fonts no))', encoding="utf-8")
        state = Path(self.temp.name) / "state"
        state.mkdir()
        self.engine = Engine([self.root / "demo.kicad_pro"], state)
        self.session = next(iter(self.engine.sessions.entries.values()))

    def edit(self, tool, **args):
        target = self.session.target(self.sheet.name)
        before = self.sheet.read_bytes()
        preview = self.engine.call(tool, dict(target, mode="preview", **args))
        if not preview["ok"] and preview["error"]["code"] == "editor_open":
            self.skipTest("Close KiCad editors for the actual file-write lifecycle")
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(before, self.sheet.read_bytes(), "Preview changed original")
        changed = self.engine.call(tool, dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        self.assertTrue(changed["ok"], changed)
        self.assertNotEqual(changed["verified"], "verification_failed", changed)
        return preview, changed

    def test_resistors_connect_measured_nets_erc_checkpoint_restore(self):
        self.edit("add_symbol", lib_id="Device:R", reference="R1", value="1k", x_mm=25.4, y_mm=50.8,
                  rotation_deg=90, mirror="x")
        self.edit("add_symbol", lib_id="Device:R", reference="R2", value="4k7", x_mm=50.8, y_mm=50.8)
        preview, _ = self.edit("connect", name="NODE", endpoints=[dict(reference="R1", pin="1"), dict(reference="R2", pin="1")])
        self.assertEqual(preview["measured_net"], "/NODE")
        self.assertEqual({(m["reference"], m["pin"]) for m in preview["net_members"]}, {("R1", "1"), ("R2", "1")})
        before = self.sheet.read_bytes()
        preview, changed = self.edit("connect", name="RETURN", endpoints=[dict(reference="R1", pin="2"), dict(reference="R2", pin="2")])
        self.assertEqual(preview["measured_net"], "/RETURN")
        self.assertEqual(changed["verified"], "erc_ok", changed)
        target = self.session.target(self.sheet.name)
        altered = self.engine.call("connect", dict(target, mode="apply", candidate_id=preview["candidate_id"], name="OTHER"))
        self.assertFalse(altered["ok"])
        restore = self.engine.call("restore_checkpoint", dict(target, mode="preview", checkpoint_id=changed["checkpoint"]["id"]))
        self.assertTrue(restore["ok"], restore)
        restored = self.engine.call("restore_checkpoint", dict(target, mode="apply", candidate_id=restore["candidate_id"]))
        self.assertTrue(restored["ok"], restored)
        self.assertEqual(self.sheet.read_bytes(), before)
        # Real replacement retains electrical anchors/UUIDs; later label still parses in KiCad.
        from pcbai.sexpr import Document
        original_symbol = Document(self.sheet.read_bytes()).root.all("symbol")[0]
        original_id = original_symbol.child("uuid").value()
        self.edit("replace_part", reference="R1", lib_id="Device:R", value="2k2")
        self.assertEqual(Document(self.sheet.read_bytes()).root.all("symbol")[0].child("uuid").value(), original_id)
        self.edit("add_label", name="GLOBAL_NODE", kind="global", x_mm=50.8, y_mm=46.99)

    def test_installed_inherited_regulator_pin_pad_multiunit_and_power_symbols(self):
        found = self.engine.call("search_parts", {"query": "AMS1117 3.3"})
        self.assertTrue(found["ok"], found)
        self.assertIn("Regulator_Linear:AMS1117-3.3", [p["lib_id"] for p in found["parts"]])
        verify = self.engine.call("verify_part", dict(symbol="Regulator_Linear:AMS1117-3.3", footprint="Package_TO_SOT_SMD:SOT-223-3_TabPin2"))
        self.assertTrue(verify["pin_pad_match"], verify)
        self.assertEqual(verify["pin_numbers"], ["1", "2", "3"])
        preview, _ = self.edit("add_symbol", lib_id="Regulator_Linear:AMS1117-3.3", reference="U1", x_mm=50.8, y_mm=50.8)
        self.assertGreater(preview["erc_after"]["errors"], 0)
        with snapshot(self.root) as copy:
            measured = parse_netlist(export_netlist(copy, "demo.kicad_sch", copy / "actual.xml"))
        self.assertIn("U1", measured["components"])
        opamp = self.engine.call("part_info", dict(lib_id="Amplifier_Operational:LM358", kind="symbol"))
        self.assertTrue(opamp["ok"], opamp)
        self.assertEqual(len({p["number"] for p in opamp["part"]["pins"]}), 8)
        for part, reference in (("GND", "#PWR"), ("PWR_FLAG", "#FLG")):
            power = self.engine.call("part_info", dict(lib_id="power:" + part, kind="symbol"))
            self.assertEqual(power["part"]["properties"]["Reference"], reference)
        self.edit("add_symbol", lib_id="power:PWR_FLAG", reference="#FLG1", x_mm=76.2, y_mm=50.8)

    def test_real_global_label_replacement_candidates_on_owned_cli_copy(self):
        """Native candidate parsing/net measurement remains safe while user GUI is open.

        This validates private fixture bytes, not the closed-editor apply lifecycle.
        """
        from pcbai.kicad.cli import rule_check
        from pcbai.sch.edit import hierarchy, plan_add_symbol, plan_labels, plan_replace
        from pcbai.sexpr import Document
        context = hierarchy(self.session, self.sheet.name)
        data = self.sheet.read_bytes()
        for ref, x in (("R1", 25.4), ("R2", 50.8)):
            data = plan_add_symbol(data, dict(lib_id="Device:R", reference=ref, value="1k", x_mm=x, y_mm=50.8), context)["data"]
        identity = Document(data).root.all("symbol")[0].child("uuid").value()
        data = plan_replace(data, dict(reference="R1", lib_id="Device:R", value="2k2"), context)["data"]
        self.assertEqual(Document(data).root.all("symbol")[0].child("uuid").value(), identity)
        for name, pin in (("A", "1"), ("B", "2")):
            data = plan_labels(data, dict(name=name, kind="global", endpoints=[dict(reference="R1", pin=pin),
                                dict(reference="R2", pin=pin)]), context, connect=True)["data"]
        data = plan_labels(data, dict(name="A", kind="global", x_mm=25.4, y_mm=46.99), context)["data"]
        checked = rule_check(self.root, self.sheet.name, "erc", override=data)
        self.assertTrue(checked["clean"], checked)
        with snapshot(self.root) as copy:
            (copy / self.sheet.name).write_bytes(data)
            netlist = parse_netlist(export_netlist(copy, self.sheet.name, copy / "native.xml"))
        self.assertEqual(netlist["components"]["R1"]["value"], "2k2")
        self.assertEqual({netlist["pins"][(ref, "1")] for ref in ("R1", "R2")}, {"A"})
        self.assertEqual({netlist["pins"][(ref, "2")] for ref in ("R1", "R2")}, {"B"})
