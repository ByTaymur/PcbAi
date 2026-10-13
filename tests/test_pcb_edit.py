import shutil
import tempfile
import unittest
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli
from pcbai.kicad.board import board, net_info, nets
from pcbai.pcb.edit import plan_move, plan_track_width, plan_zone
from pcbai.sexpr import Document
from pcbai.tools.engine import Engine
from pcbai.views import scene_pcb

BOARD = b"""(kicad_pcb (version 20260206) (generator "pcbnew")
  (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (5 "F.SilkS" user "F.Silkscreen") (7 "B.SilkS" user "B.Silkscreen")
    (25 "Edge.Cuts" user))
  (footprint "Demo" (layer "F.Cu") (uuid "fp1") (at 10 20 90)
    (property "Reference" "R1" (at 0 -2 90) (layer "F.SilkS") (uuid "ref1") (effects (font (size 1 1))))
    (fp_line (start -1 -1) (end 3 -1) (layer "F.SilkS") (uuid "ln1"))
    (pad "1" smd rect (at 2 0.5 90) (size 1 1) (layers "F.Cu" "F.Mask") (net "VCC") (uuid "p1")))
  (segment (start 10 18) (end 20 18) (width 0.25) (layer "F.Cu") (net "VCC") (uuid "t1"))
  (segment (start 20 18) (end 30 18) (width 0.25) (layer "F.Cu") (net "GND") (uuid "t2"))
  (gr_rect (start 0 0) (end 40 30) (layer "Edge.Cuts") (uuid "edge")))
"""


class PlannerTests(unittest.TestCase):
    def test_translation_changes_only_the_position_atoms(self):
        plan = plan_move(BOARD, "R1", x=12.5, y=21)
        before, after = BOARD, plan["data"]
        prefix = next(i for i, (a, b) in enumerate(zip(before, after, strict=False)) if a != b)
        self.assertEqual(before[:prefix], after[:prefix])
        self.assertIn(b"(at 12.5 21 90)", after)
        self.assertEqual(before.replace(b"(at 10 20 90)", b"(at 12.5 21 90)"), after)
        self.assertEqual(plan["before"]["at"], [10, 20])

    def test_rotation_moves_absolute_pad_and_text_angles(self):
        data = plan_move(BOARD, "R1", rotation=180)["data"]
        self.assertIn(b"(at 10 20 180)", data)
        self.assertIn(b"(at 2 0.5 180)", data)  # pad angle is board-absolute: 90 + 90
        self.assertIn(b"(at 0 -2 180)", data)
        self.assertIn(b"(start -1 -1) (end 3 -1)", data)  # local graphics unchanged
        pad = next(i for i in scene_pcb(data)["items"] if i["uuid"] == "p1")
        self.assertEqual([round(v, 6) for v in pad["at"]], [8, 19.5])  # local (2, 0.5) turned 180°

    def test_flip_swaps_layers_mirrors_local_y_and_text(self):
        data = plan_move(BOARD, "R1", side="back")["data"]
        doc = Document(data)
        fp = doc.root.child("footprint")
        self.assertEqual(fp.child("layer").value(), "B.Cu")
        self.assertIn(b'(layers "B.Cu" "B.Mask")', data)
        self.assertIn(b'(layer "B.SilkS")', data)
        self.assertIn(b"(start -1 1) (end 3 1)", data)
        self.assertIn(b"(at 10 20 90)", data)  # 180 - 90
        self.assertIn(b"(justify mirror)", data)
        back = plan_move(data, "R1", side="front")["data"]
        self.assertNotIn(b"mirror", back)
        self.assertEqual(Document(back).root.child("footprint").child("layer").value(), "F.Cu")

    def test_unsupported_and_unknown_footprints_refused(self):
        with self.assertRaises(PcbAiError) as raised:
            plan_move(BOARD.replace(b'(uuid "ln1"))', b'(uuid "ln1")) (zone (net "VCC"))'), "R1", x=1)
        self.assertEqual(raised.exception.code, "unsupported_edit")
        with self.assertRaises(PcbAiError):
            plan_move(BOARD, "R9", x=1)

    def test_track_width_by_net_or_uuid(self):
        plan = plan_track_width(BOARD, 0.5, net="VCC")
        self.assertEqual(plan["tracks"], ["t1"])
        self.assertIn(b'(width 0.5) (layer "F.Cu") (net "VCC")', plan["data"])
        self.assertIn(b'(width 0.25) (layer "F.Cu") (net "GND")', plan["data"])
        self.assertEqual(plan_track_width(BOARD, 1, uuids=["t2"])["tracks"], ["t2"])
        for kwargs in (dict(net="NOPE"), dict(uuids=["zz"]), dict()):
            with self.assertRaises(PcbAiError):
                plan_track_width(BOARD, 0.5, **kwargs)
        with self.assertRaises(PcbAiError):
            plan_track_width(BOARD, 0, net="VCC")

    def test_zone_formats_and_validation(self):
        plan = plan_zone(BOARD, "GND", "B.Cu", [[1, 1], [39, 1], [39, 29], [1, 29]])
        zone = next(z for z in Document(plan["data"]).root.all("zone"))
        self.assertEqual(zone.child("net").value(), "GND")  # KiCad 10 named net
        self.assertEqual(zone.child("filled_areas_thickness").value(), "no")
        self.assertEqual(round(plan["area_mm2"]), 38 * 28)
        old = BOARD.replace(b"(layers", b'(net 0 "") (net 1 "GND") (layers', 1)
        numbered = plan_zone(old, "GND", "F.Cu", [[1, 1], [5, 1], [5, 5]])["data"]
        self.assertIn(b'(net 1) (net_name "GND")', numbered)
        for args in (("NOPE", "F.Cu"), ("GND", "F.SilkS")):
            with self.assertRaises(PcbAiError):
                plan_zone(BOARD, *args, [[1, 1], [5, 1], [5, 5]])
        with self.assertRaises(PcbAiError):
            plan_zone(BOARD, "GND", "F.Cu", [[1, 1], [2, 2], [3, 3]])


class KiCad10NetTests(unittest.TestCase):
    def test_named_nets_in_scene_list_and_info(self):
        scene = scene_pcb(BOARD)
        self.assertEqual({i["uuid"]: i["net"] for i in scene["items"] if i["type"] in {"pad", "track"}},
                         {"p1": "VCC", "t1": "VCC", "t2": "GND"})
        self.assertEqual([n["name"] for n in nets(board(BOARD))], ["GND", "VCC"])
        info = net_info(BOARD, "VCC")
        self.assertEqual((len(info["pads"]), info["track_segment_count"]), (1, 1))


def demos():
    try:
        cli = Path(find_kicad_cli())
    except PcbAiError:
        return None
    path = cli.parent.parent / "share/kicad/demos"
    return path if (path / "ecc83").is_dir() else None


def editors_closed():
    from pcbai.kicad.files import assert_closed
    try:
        assert_closed(Path(tempfile.gettempdir()) / "pcbai-no-such-project")
        return True
    except PcbAiError:
        return False


@unittest.skipUnless(demos(), "KiCad demos required")
class OracleTests(unittest.TestCase):
    def test_moves_match_kicad_pcbnew_on_ecc83(self):
        from scripts.oracle_fp_check import check, kicad_python

        python = kicad_python()
        if python is None:
            self.skipTest("KiCad Python not found")
        with tempfile.TemporaryDirectory(prefix="pcbai-oracle-test-") as tmp:
            copy = Path(tmp) / "ecc83"
            shutil.copytree(demos() / "ecc83", copy)
            work = Path(tmp) / "work"
            work.mkdir()
            outcome = check(copy / "ecc83-pp.kicad_pcb", work, python)
            self.assertEqual(outcome["problems"], [])
            self.assertEqual(outcome["refused"], [])
            self.assertGreaterEqual(outcome["ops"], 15)


@unittest.skipUnless(demos() and editors_closed(), "KiCad demos required and KiCad editors must be closed")
class EngineEditTests(unittest.TestCase):
    def open(self, demo, document):
        tmp = tempfile.TemporaryDirectory(prefix="pcbai-pcbedit-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / demo
        shutil.copytree(demos() / demo, root)
        state = Path(tmp.name) / "state"
        state.mkdir()
        self.engine = Engine([next(root.glob("*.kicad_pro"))], state)
        self.session = next(iter(self.engine.sessions.entries.values()))
        self.document = document
        self.path = root / document

    def edit(self, tool, **args):
        target = self.session.target(self.document)
        preview = self.engine.call(tool, dict(target, mode="preview", **args))
        self.assertTrue(preview["ok"], preview)
        applied = self.engine.call(tool, dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        return preview, applied

    def test_move_that_breaks_tracks_is_blocked_and_file_untouched(self):
        self.open("ecc83", "ecc83-pp.kicad_pcb")
        original = self.path.read_bytes()
        fp = next(i for i in scene_pcb(original)["items"] if i["type"] == "footprint" and i["reference"] == "R1")
        preview, applied = self.edit("move_footprint", reference="R1", x_mm=fp["at"][0] - 2)
        self.assertGreater(preview["drc_after"]["errors"], preview["drc_before"]["errors"])
        self.assertTrue(preview["warnings"])
        self.assertEqual(applied["error"]["code"], "new_violations")
        self.assertEqual(self.path.read_bytes(), original)

    def test_marker_on_footprint_moved_to_done_and_restore_is_byte_equal(self):
        self.open("pic_programmer", "pic_programmer.kicad_pcb")
        original = self.path.read_bytes()
        fp = next(i for i in scene_pcb(original)["items"] if i["type"] == "footprint" and i["reference"] == "P101")
        target = self.session.target(self.document)
        current = self.engine.call("get_markers", {"session": self.session.id})
        marker = dict(kind="item", space="pcb", points_mm=[fp["at"]], note="#1 P101'i 1 mm sağa al",
                      anchor=dict(type="footprint", uuid=fp["uuid"]))
        preview = self.engine.call("set_marker", dict(target, mode="preview", marker=marker,
                                                      markers_revision=current["markers_revision"]), source="view")
        self.engine.call("set_marker", dict(target, mode="apply", candidate_id=preview["candidate_id"],
                                            markers_revision=current["markers_revision"]), source="view")
        read = self.engine.call("get_markers", {"session": self.session.id})["markers"][0]
        self.assertEqual(read["target_item"]["reference"], "P101")
        moved, applied = self.edit("move_footprint", reference=read["target_item"]["reference"],
                                   x_mm=fp["at"][0] + 1)
        self.assertTrue(applied["ok"], applied)
        self.assertLessEqual(moved["drc_after"]["errors"], moved["drc_before"]["errors"])
        status = self.engine.call("update_marker_status", dict(
            applied["target"], mode="preview", n=read["n"], status="done", reason="P101 moved 1 mm right",
            evidence_id=applied["change_id"],
            markers_revision=self.engine.call("get_markers", {"session": self.session.id})["markers_revision"]))
        self.assertTrue(status["ok"], status)
        done = self.engine.call("update_marker_status", dict(applied["target"], mode="apply",
                                candidate_id=status["candidate_id"], markers_revision=status["markers_revision"]))
        self.assertTrue(done["ok"], done)
        final = self.engine.call("get_markers", {"session": self.session.id})["markers"][0]
        self.assertEqual((final["status"], final["binding"]), ("done", "bound"))
        self.assertAlmostEqual(final["points_mm"][0][0], fp["at"][0] + 1, places=6)
        restore = self.engine.call("restore_checkpoint", dict(self.session.target(self.document), mode="preview",
                                                              checkpoint_id=applied["checkpoint"]["id"]))
        self.engine.call("restore_checkpoint", dict(self.session.target(self.document), mode="apply",
                                                    candidate_id=restore["candidate_id"]))
        self.assertEqual(self.path.read_bytes(), original)

    def test_track_width_and_zone_with_real_drc(self):
        self.open("ecc83", "ecc83-pp.kicad_pcb")
        scene = scene_pcb(self.path.read_bytes())
        track = next(i for i in scene["items"] if i["type"] == "track" and i["net"] and i["width"] >= 0.5)
        preview, applied = self.edit("set_track_width", uuids=[track["uuid"]], width_mm=track["width"] - 0.1)
        self.assertEqual(preview["tracks"], [track["uuid"]])
        self.assertTrue(applied["ok"], applied)
        saved = scene_pcb(self.path.read_bytes())
        self.assertEqual(next(i for i in saved["items"] if i["uuid"] == track["uuid"])["width"],
                         round(track["width"] - 0.1, 6))
        x0, y0, x1, y1 = scene["bbox"]
        outline = [[x0 + 1, y0 + 1], [x1 - 1, y0 + 1], [x1 - 1, y1 - 1], [x0 + 1, y1 - 1]]
        # ecc83 already has a GND zone on B.Cu: an overlapping one is a real zones_intersect error.
        before = self.path.read_bytes()
        blocked, refused = self.edit("add_zone", net="GND", layer="B.Cu", points_mm=outline)
        self.assertEqual(blocked["drc_after"]["errors"], blocked["drc_before"]["errors"] + 1)
        self.assertEqual(refused["error"]["code"], "new_violations")
        self.assertEqual(self.path.read_bytes(), before)
        zone, applied = self.edit("add_zone", net="GND", layer="F.Cu", points_mm=outline)
        self.assertGreater(zone["filled_polygons"], 0)
        self.assertEqual(zone["drc_after"]["errors"], zone["drc_before"]["errors"])
        self.assertTrue(applied["ok"], applied)
        after = self.path.read_bytes()
        self.assertEqual(after[:len(before) - 3], before[:len(before) - 3])  # only the zone is appended
        new = [z for z in Document(after).root.all("zone") if z.child("uuid").value() == zone["zone_uuid"]]
        self.assertEqual(len(new), 1)
        self.assertTrue(new[0].all("filled_polygon"))
        self.assertEqual(applied["verified"], "drc_findings")  # ecc83 keeps its two pre-existing warnings


    def mark(self, marker):
        target = self.session.target(self.document)
        current = self.engine.call("get_markers", {"session": self.session.id})
        preview = self.engine.call("set_marker", dict(target, mode="preview", marker=marker,
                                                      markers_revision=current["markers_revision"]), source="view")
        self.assertTrue(preview["ok"], preview)
        saved = self.engine.call("set_marker", dict(target, mode="apply", candidate_id=preview["candidate_id"],
                                                    markers_revision=current["markers_revision"]), source="view")
        self.assertTrue(saved["ok"], saved)
        return saved["marker"]["n"]

    def done(self, n, applied, reason):
        revision = self.engine.call("get_markers", {"session": self.session.id})["markers_revision"]
        status = self.engine.call("update_marker_status", dict(applied["target"], mode="preview", n=n, status="done",
                                  reason=reason, evidence_id=applied["change_id"], markers_revision=revision))
        self.assertTrue(status["ok"], status)
        final = self.engine.call("update_marker_status", dict(applied["target"], mode="apply",
                                 candidate_id=status["candidate_id"], markers_revision=status["markers_revision"]))
        self.assertTrue(final["ok"], final)

    def test_track_and_area_markers_applied_to_done_then_restored(self):
        """Section 4 acceptance: "#2 bu hat … olsun" and "#3 buraya GND dökümü" end as done with DRC evidence."""
        self.open("ecc83", "ecc83-pp.kicad_pcb")
        original = self.path.read_bytes()
        scene = scene_pcb(original)
        track = next(i for i in scene["items"] if i["type"] == "track" and i["net"] and i["width"] >= 0.5)
        line = self.mark(dict(kind="line", space="pcb", layer=track["layer"], points_mm=track["points"][:2],
                              note=f"#2 bu hat {track['width'] - 0.1:g} mm olsun",
                              anchor=dict(type="track", uuid=track["uuid"])))
        x0, y0, x1, y1 = scene["bbox"]
        outline = [[x0 + 1, y0 + 1], [x1 - 1, y0 + 1], [x1 - 1, y1 - 1], [x0 + 1, y1 - 1]]
        area = self.mark(dict(kind="area", space="pcb", layer="F.Cu", points_mm=outline,
                              note="#3 buraya GND dökümü"))
        markers = {m["n"]: m for m in self.engine.call("get_markers", {"session": self.session.id})["markers"]}
        self.assertEqual(markers[line]["target_item"]["type"], "track")
        _, first = self.edit("set_track_width", uuids=[markers[line]["anchor"]["uuid"]], width_mm=track["width"] - 0.1)
        self.assertTrue(first["ok"], first)
        self.done(line, first, "track narrowed; DRC errors unchanged")
        _, second = self.edit("add_zone", net="GND", layer=markers[area]["layer"], points_mm=markers[area]["points_mm"])
        self.assertTrue(second["ok"], second)
        self.done(area, second, "GND zone added and filled by KiCad")
        final = {m["n"]: m for m in self.engine.call("get_markers", {"session": self.session.id})["markers"]}
        self.assertEqual([final[line]["status"], final[area]["status"]], ["done", "done"])
        self.assertEqual(final[area]["evidence_id"], second["change_id"])
        restore = self.engine.call("restore_checkpoint", dict(self.session.target(self.document), mode="preview",
                                                              checkpoint_id=first["checkpoint"]["id"]))
        self.engine.call("restore_checkpoint", dict(self.session.target(self.document), mode="apply",
                                                    candidate_id=restore["candidate_id"]))
        self.assertEqual(self.path.read_bytes(), original)


class NetclassPlannerTests(unittest.TestCase):
    PROJECT = ('{\r\n  "net_settings": {\r\n    "classes": [\r\n      {\r\n        "clearance": 0.2,\r\n'
               '        "name": "Default",\r\n        "priority": 2147483647,\r\n        "track_width": 0.25,\r\n'
               '        "via_diameter": 0.8,\r\n        "via_drill": 0.4\r\n      }\r\n    ],\r\n'
               '    "netclass_patterns": []\r\n  }\r\n}\r\n').encode()

    def test_create_update_and_assign_keep_format(self):
        from pcbai.pcb.netclass import plan_netclass

        plan = plan_netclass(self.PROJECT, "POWER", {"track_width_mm": 0.8, "clearance_mm": 0.3}, ["GND", "VCC"])
        self.assertTrue(plan["created"])
        import json
        project = json.loads(plan["data"])
        power = next(c for c in project["net_settings"]["classes"] if c["name"] == "POWER")
        self.assertEqual((power["track_width"], power["clearance"], power["priority"]), (0.8, 0.3, 0))
        self.assertEqual(project["net_settings"]["netclass_patterns"],
                         [{"netclass": "POWER", "pattern": "GND"}, {"netclass": "POWER", "pattern": "VCC"}])
        self.assertNotIn(b"\n", plan["data"].replace(b"\r\n", b""))  # CRLF kept
        again = plan_netclass(plan["data"], "POWER", {"via_drill_mm": 0.3})
        self.assertFalse(again["created"])
        self.assertEqual(again["old"]["via_drill_mm"], 0.4)

    def test_refusals(self):
        from pcbai.pcb.netclass import plan_netclass

        with self.assertRaises(PcbAiError):
            plan_netclass(self.PROJECT.replace(b"  ", b"   "), "X", {"clearance_mm": 0.1})  # foreign formatting
        with self.assertRaises(PcbAiError):
            plan_netclass(self.PROJECT, "Default", {"via_drill_mm": 0.9})  # drill ≥ diameter
        with self.assertRaises(PcbAiError):
            plan_netclass(self.PROJECT, "", {"clearance_mm": 0.1})
        with self.assertRaises(PcbAiError):
            plan_netclass(self.PROJECT, "X", {"track_width_mm": 0})


@unittest.skipUnless(demos() and editors_closed(), "KiCad demos required and KiCad editors must be closed")
class NetclassEngineTests(unittest.TestCase):
    def test_power_class_change_with_real_drc_and_byte_equal_restore(self):
        with tempfile.TemporaryDirectory(prefix="pcbai-netclass-") as tmp:
            root = Path(tmp) / "pic"
            shutil.copytree(demos() / "pic_programmer", root)
            state = Path(tmp) / "state"
            state.mkdir()
            engine = Engine([root / "pic_programmer.kicad_pro"], state)
            session = next(iter(engine.sessions.entries.values()))
            project = root / "pic_programmer.kicad_pro"
            original = project.read_bytes()
            target = session.target(project.name)
            wide = engine.call("set_netclass", dict(target, mode="preview", netclass="POWER", clearance_mm=1.0))
            self.assertGreater(wide["drc_after"]["errors"], wide["drc_before"]["errors"])  # the class reaches DRC
            refused = engine.call("set_netclass", dict(target, mode="apply", candidate_id=wide["candidate_id"]))
            self.assertEqual(refused["error"]["code"], "new_violations")
            self.assertEqual(project.read_bytes(), original)
            preview = engine.call("set_netclass", dict(target, mode="preview", netclass="POWER", clearance_mm=0.25))
            self.assertTrue(preview["ok"], preview)
            self.assertEqual(preview["check_document"], "pic_programmer.kicad_pcb")
            self.assertEqual(preview["drc_after"]["errors"], preview["drc_before"]["errors"])
            applied = engine.call("set_netclass", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
            self.assertTrue(applied["ok"], applied)
            self.assertIn(b'"clearance": 0.25', project.read_bytes())
            restore = engine.call("restore_checkpoint", dict(session.target(project.name), mode="preview",
                                                             checkpoint_id=applied["checkpoint"]["id"]))
            self.assertTrue(restore["ok"], restore)
            done = engine.call("restore_checkpoint", dict(session.target(project.name), mode="apply",
                                                          candidate_id=restore["candidate_id"]))
            self.assertTrue(done["ok"], done)
            self.assertEqual(project.read_bytes(), original)
