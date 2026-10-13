import math
import shutil
import tempfile
import unittest
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli
from pcbai.sch.scene import hit_test_sch, orient, parse_netlist, place, scene_sch
from pcbai.tools.engine import Engine
from tests.helpers import make_project

LIB = b'''(lib_symbols
  (symbol "Demo:U" (property "Reference" "U")
    (symbol "U_0_1" (rectangle (start -2.54 2.54) (end 2.54 -2.54)))
    (symbol "U_1_1" (pin input line (at -5.08 1.27 0) (length 2.54) (name "A") (number "1")))
    (symbol "U_2_1" (pin output line (at 5.08 -1.27 180) (length 2.54) (name "Y") (number "2"))
      (pin power_in line (at 0 5.08 270) (length 2.54) (hide yes) (name "VCC") (number "3")))))'''


def schematic(symbols, extra=b""):
    return (b'(kicad_sch (version 20250114) (generator "eeschema") (uuid "root") (paper "A4") '
            + LIB + symbols + extra + b")")


def symbol(uuid, at, rotation=0, mirror=None, unit=1, instances=None):
    mirror_text = f"(mirror {mirror})" if mirror else ""
    records = instances or [("/root", "U1", unit)]
    paths = "".join(f'(path "{p}" (reference "{r}") (unit {u}))' for p, r, u in records)
    return (f'(symbol (lib_id "Demo:U") (at {at[0]} {at[1]} {rotation}) {mirror_text} (unit {unit}) '
            f'(uuid "{uuid}") (property "Reference" "U?") (property "Value" "74HC00") '
            f'(pin "1" (uuid "{uuid}-p1")) (pin "2" (uuid "{uuid}-p2")) '
            f'(instances (project "Test" {paths})))').encode()


class OrientationTests(unittest.TestCase):
    def test_library_y_up_rotation_then_mirror(self):
        local = [2.54, 1.27]
        expected = {
            (0, None): [2.54, -1.27], (90, None): [-1.27, -2.54], (180, None): [-2.54, 1.27],
            (270, None): [1.27, 2.54], (0, "x"): [2.54, 1.27], (0, "y"): [-2.54, -1.27],
            (90, "x"): [-1.27, 2.54], (90, "y"): [1.27, -2.54],
        }
        for (rotation, mirror), offset in expected.items():
            with self.subTest(rotation=rotation, mirror=mirror):
                result = orient(local, rotation, mirror)
                self.assertLess(math.dist(result, offset), 1e-9)
        self.assertEqual(place(local, [100, 50], 0, None), [102.54, 48.73])


class SceneTests(unittest.TestCase):
    def test_unit_pins_instance_reference_and_hidden_flag(self):
        data = schematic(symbol("s1", [100, 100], unit=2, instances=[("/root", "U7", 2)]))
        scene = scene_sch(data, "/root")
        pins = {p["number"]: p for p in scene["items"] if p["type"] == "pin"}
        self.assertEqual(set(pins), {"2", "3"})  # unit 2 plus nothing from unit 1
        self.assertEqual(pins["2"]["at"], [105.08, 101.27])
        self.assertTrue(pins["3"]["hidden"])
        self.assertEqual(pins["2"]["reference"], "U7")
        self.assertEqual(pins["2"]["uuid"], "s1-p2")
        sym = next(i for i in scene["items"] if i["type"] == "symbol")
        self.assertEqual(sym["bbox"][0] <= 97.46 <= sym["bbox"][2], True)

    def test_shared_sheet_instances_use_their_own_reference(self):
        data = schematic(symbol("s1", [50, 50], instances=[("/root/a", "R203", 1), ("/root/b", "R303", 1)]))
        first = [i for i in scene_sch(data, "/root/a")["items"] if i["type"] == "symbol"]
        second = [i for i in scene_sch(data, "/root/b")["items"] if i["type"] == "symbol"]
        self.assertEqual([first[0]["reference"], second[0]["reference"]], ["R203", "R303"])
        self.assertEqual(scene_sch(data, "/root/other")["items"], [])

    def test_wire_and_label_nets_come_from_netlisted_pins_only(self):
        wires = (b'(wire (pts (xy 94.92 98.73) (xy 80 98.73)) (uuid "w1"))'
                 b'(wire (pts (xy 80 98.73) (xy 80 90)) (uuid "w2"))'
                 b'(label "IN" (at 80 90 0) (uuid "l1"))'
                 b'(wire (pts (xy 10 10) (xy 20 10)) (uuid "lonely"))')
        data = schematic(symbol("s1", [100, 100]), wires)
        netlist = dict(pins={("U1", "1"): "/IN"}, members={"/IN": [], "/X": []},
                       pages=[dict(names="/", tstamps="/")])
        items = {i["uuid"]: i for i in scene_sch(data, "/root", netlist)["items"]}
        self.assertEqual(items["s1-p1"]["net"], "/IN")
        self.assertEqual(items["w1"]["net"], "/IN")
        self.assertEqual(items["w2"]["net"], "/IN")  # T/end connection propagates
        self.assertEqual(items["l1"]["net"], "/IN")
        self.assertIsNone(items["lonely"]["net"])

    def test_label_net_only_when_that_exact_name_is_netlisted(self):
        extra = (b'(wire (pts (xy 10 10) (xy 20 10)) (uuid "w1")) (label "CLK" (at 10 10 0) (uuid "l1"))'
                 b'(wire (pts (xy 10 30) (xy 20 30)) (uuid "w2")) (label "NOPE" (at 10 30 0) (uuid "l2"))')
        data = schematic(b"", extra)
        netlist = dict(pins={}, members={"/a/CLK": []}, pages=[dict(names="/a/", tstamps="/a/")])
        items = {i["uuid"]: i for i in scene_sch(data, "/root/a", netlist)["items"]}
        self.assertEqual(items["w1"]["net"], "/a/CLK")
        self.assertIsNone(items["w2"]["net"])

    def test_conflicting_pins_leave_wire_unknown(self):
        extra = b'(wire (pts (xy 94.92 98.73) (xy 105.08 101.27)) (uuid "w"))'
        data = schematic(symbol("s1", [100, 100]) + symbol("s2", [100, 100], unit=2,
                                                            instances=[("/root", "U2", 2)]), extra)
        netlist = dict(pins={("U1", "1"): "A", ("U2", "2"): "B"}, members={}, pages=[])
        scene = scene_sch(data, "/root", netlist)
        self.assertIsNone(next(i for i in scene["items"] if i["uuid"] == "w")["net"])
        self.assertTrue(any("different KiCad nets" in w for w in scene["warnings"]))

    def test_hit_prefers_pin_at_connection_point(self):
        scene = scene_sch(schematic(symbol("s1", [100, 100])), "/root")
        hits = hit_test_sch(scene, 94.92, 98.73)
        self.assertEqual(hits[0]["type"], "pin")
        self.assertEqual(hit_test_sch(scene, 100, 100)[0]["type"], "symbol")
        with self.assertRaises(PcbAiError):
            hit_test_sch(scene, float("nan"), 0)

    def test_netlist_rejects_entities_and_parses_members(self):
        with self.assertRaises(PcbAiError):
            parse_netlist(b'<!DOCTYPE x [<!ENTITY a "b">]><export/>')
        data = (b'<export><design><sheet number="1" name="/" tstamps="/"><title_block><source>a.kicad_sch'
                b'</source></title_block></sheet></design><components><comp ref="R1"><value>1k</value>'
                b'<sheetpath names="/" tstamps="/"/></comp></components><nets><net code="1" name="GND">'
                b'<node ref="R1" pin="2"/></net></nets></export>')
        netlist = parse_netlist(data)
        self.assertEqual(netlist["pins"][("R1", "2")], "GND")
        self.assertEqual(netlist["members"]["GND"][0]["sheet"], "/")


def demo_root():
    try:
        cli = Path(find_kicad_cli())
    except PcbAiError:
        return None
    path = cli.parent.parent / "share/kicad/demos/complex_hierarchy"
    return path if path.is_dir() else None


@unittest.skipUnless(demo_root(), "Installed KiCad complex_hierarchy demo required")
class SchematicViewIntegrationTests(unittest.TestCase):
    def test_complex_hierarchy_instances_pages_and_nets(self):
        with tempfile.TemporaryDirectory(prefix="pcbai-g2-") as tmp:
            root = Path(tmp) / "project"
            shutil.copytree(demo_root(), root)
            state = Path(tmp) / "state"
            state.mkdir()
            project = root / "complex_hierarchy.kicad_pro"
            engine = Engine([project], state)
            session = next(iter(engine.sessions.entries.values()))
            target = session.target("complex_hierarchy.kicad_sch")
            rendered = engine.call("render_sch", target)
            self.assertTrue(rendered["ok"], rendered)
            pages = rendered["render"]["pages"]
            self.assertEqual([p["names"] for p in pages], ["/", "/ampli_ht_vertical/", "/ampli_ht_horizontal/"])
            self.assertEqual(len({p["sha256"] for p in pages}), 3)
            references = {}
            nets = {}
            for page in pages:
                scene = engine.call("scene_sch", dict(target, sheet=page["instance"]))
                self.assertTrue(scene["ok"], scene)
                for item in scene["scene"]["items"]:
                    if item["type"] == "symbol" and item["reference"].startswith("R"):
                        references.setdefault(page["names"], set()).add(item["reference"])
                    if item["type"] == "pin" and item["net"]:
                        nets.setdefault(item["net"], set()).add((item["reference"], item["number"]))
            self.assertIn("R203", references["/ampli_ht_vertical/"])
            self.assertIn("R303", references["/ampli_ht_horizontal/"])
            self.assertNotIn("R303", references["/ampli_ht_vertical/"])
            netlist = engine.netlists[(session.id, "complex_hierarchy.kicad_sch", target["revision"])]
            for name, members in netlist["members"].items():
                self.assertEqual(nets.get(name, set()), {(m["reference"], m["pin"]) for m in members}, name)
            sub = engine.call("scene_sch", dict(session.target("ampli_ht.kicad_sch"), sheet=pages[1]["instance"]))
            self.assertEqual(sub["error"]["code"], "invalid_document")
            self.assertEqual(session.target("complex_hierarchy.kicad_sch"), target)


class EngineGuardTests(unittest.TestCase):
    def test_unknown_sheet_and_pcb_document_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp) / "p")
            state = Path(tmp) / "state"
            state.mkdir()
            engine = Engine([project], state)
            session = next(iter(engine.sessions.entries.values()))
            response = engine.call("scene_sch", dict(session.target("Test.kicad_pcb"), sheet="/x"))
            self.assertEqual(response["error"]["code"], "invalid_document")


def editors_closed():
    try:
        from pcbai.kicad.files import assert_closed
        assert_closed(Path(tempfile.gettempdir()) / "pcbai-no-such-project")
        return True
    except PcbAiError:
        return False


@unittest.skipUnless(demo_root() and editors_closed(), "KiCad demo required and KiCad editors must be closed")
class SchematicMarkerFlowTests(unittest.TestCase):
    def test_marker_on_r203_drives_real_value_edit_to_done(self):
        """G2-f: "#1 bu direnç 4,7k olsun" read by the agent, applied with set_value, completed with evidence."""
        with tempfile.TemporaryDirectory(prefix="pcbai-g2f-") as tmp:
            root = Path(tmp) / "project"
            shutil.copytree(demo_root(), root)
            state = Path(tmp) / "state"
            state.mkdir()
            engine = Engine([root / "complex_hierarchy.kicad_pro"], state)
            session = next(iter(engine.sessions.entries.values()))
            top = session.target("complex_hierarchy.kicad_sch")
            pages = engine.call("render_sch", top)["render"]["pages"]
            vertical = next(p for p in pages if p["names"] == "/ampli_ht_vertical/")
            scene = engine.call("scene_sch", dict(top, sheet=vertical["instance"]))["scene"]
            r203 = next(i for i in scene["items"] if i["type"] == "symbol" and i["reference"] == "R203")
            target = session.target("ampli_ht.kicad_sch")
            markers = engine.call("get_markers", {"session": session.id})
            marker = dict(kind="item", space="sch", sheet=vertical["instance"], points_mm=[r203["at"]],
                          note="bu direnç 4,7k olsun", anchor=dict(type="symbol", uuid=r203["uuid"]))
            preview = engine.call("set_marker", dict(target, mode="preview", marker=marker,
                                                     markers_revision=markers["markers_revision"]), source="view")
            self.assertTrue(preview["ok"], preview)
            saved = engine.call("set_marker", dict(target, mode="apply", candidate_id=preview["candidate_id"],
                                                   markers_revision=markers["markers_revision"]), source="view")
            self.assertTrue(saved["ok"], saved)
            # Agent side: only MCP-visible tools from here on.
            read = engine.call("get_markers", {"session": session.id})["markers"][0]
            self.assertEqual((read["binding"], read["target_item"]["reference"]), ("bound", "R203"))
            edit = engine.call("set_value", dict(session.target(read["document"]), mode="preview",
                                                 reference=read["target_item"]["reference"], value="4k7"))
            self.assertTrue(edit["ok"], edit)
            self.assertEqual(edit["affected_references"], ["R203", "R303"])  # shared file: both instances
            applied = engine.call("set_value", dict(session.target(read["document"]), mode="apply",
                                                    candidate_id=edit["candidate_id"]))
            self.assertTrue(applied["ok"], applied)
            self.assertEqual(applied["verified"].split("_")[0], "erc")
            current = engine.call("get_markers", {"session": session.id})
            status = engine.call("update_marker_status", dict(
                applied["target"], mode="preview", n=read["n"], status="done", reason="R203 = 4k7 (set_value)",
                evidence_id=applied["change_id"], markers_revision=current["markers_revision"]))
            self.assertTrue(status["ok"], status)
            done = engine.call("update_marker_status", dict(
                applied["target"], mode="apply", candidate_id=status["candidate_id"],
                markers_revision=status["markers_revision"]))
            self.assertTrue(done["ok"], done)
            final = engine.call("get_markers", {"session": session.id})["markers"][0]
            self.assertEqual((final["status"], final["evidence_id"], final["binding"]),
                             ("done", applied["change_id"], "bound"))
            self.assertEqual(final["target_item"]["value"], "4k7")
