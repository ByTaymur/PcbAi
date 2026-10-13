import math
import tempfile
import unittest
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.tools.engine import Engine
from pcbai.view_render import apply_matrix, inverse, svg_metadata
from pcbai.views import scene_pcb, hit_test, arc_points
from tests.helpers import make_project

GEOMETRY = b"""(kicad_pcb (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user))
 (net 1 "GND")
 (footprint "Demo" (uuid "front") (at 10 20 90) (layer "F.Cu")
  (property "Reference" "R1") (property "Value" "10k")
  (fp_rect (start -1 -1) (end 4 1) (layer "F.CrtYd"))
  (pad "1" smd circle (at 2 0 90) (size 1 1) (layers "F.Cu") (net 1 "GND") (uuid "p1")))
 (footprint "Demo" (uuid "back") (at 30 20 90) (layer "B.Cu")
  (property "Reference" "R2") (property "Value" "4k7")
  (pad "1" smd rect (at -2 0 90) (size 1 2) (layers "B.Cu") (uuid "p2")))
 (segment (start 10 18) (end 20 18) (width .4) (layer "F.Cu") (net 1) (uuid "track"))
 (via (at 20 18) (size 1) (drill .3) (layers "F.Cu" "B.Cu") (uuid "via"))
 (zone (net 1) (layer "B.Cu") (uuid "zone") (polygon (pts (xy 0 0) (xy 40 0) (xy 40 30) (xy 0 30))))
 (gr_rect (start 0 0) (end 40 30) (layer "Edge.Cuts") (uuid "edge")))"""


class SceneTests(unittest.TestCase):
    def test_rotation_saved_backside_and_visible_layer_hits(self):
        scene = scene_pcb(GEOMETRY)
        pads = {i["uuid"]: i for i in scene["items"] if i["type"] == "pad"}
        self.assertEqual(pads["p1"]["at"], [10, 18])
        self.assertEqual(pads["p2"]["at"], [30, 22])
        self.assertEqual(pads["p1"]["net"], "GND")
        self.assertEqual(hit_test(scene, 10, 18, ["F.Cu"])[0]["uuid"], "p1")
        self.assertNotIn("p2", [i["uuid"] for i in hit_test(scene, 30, 22, ["F.Cu"])])
        self.assertEqual(hit_test(scene, 15, 18, ["F.Cu"])[0]["uuid"], "track")
        self.assertEqual(hit_test(scene, 20, 18, ["B.Cu"])[0]["uuid"], "via")
        self.assertEqual(hit_test(scene, 5, 5, ["B.Cu"])[0]["uuid"], "zone")

    def test_arc_distance_and_empty_bad_nonfinite_scene(self):
        points = arc_points([1, 0], [0, 1], [-1, 0])
        self.assertTrue(any(abs(p[1] - 1) < 0.01 for p in points))
        with self.assertRaises(PcbAiError):
            scene_pcb(GEOMETRY.replace(b"(at 10 20 90)", b"(at nan 20 90)"))
        with self.assertRaises(PcbAiError):
            scene_pcb(b"(kicad_pcb)")

    def test_inverse_general_affine_roundtrip(self):
        m = [1.2, 0.3, -0.1, 2, -121.1, 90]
        point = [42.4, 120.6]
        recovered = apply_matrix(inverse(m), apply_matrix(m, point))
        self.assertLess(math.dist(point, recovered), 1e-10)
        with self.assertRaises(PcbAiError):
            inverse([0, 0, 0, 0, 0, 0])

    def test_svg_active_content_and_invalid_dimensions_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.svg"
            for content in [
                '<svg viewBox="0 0 1 1"><script/></svg>',
                '<svg viewBox="0 0 1 1"><image href="https://example.org"/></svg>',
                '<svg viewBox="0 0 nan 1"/>',
                '<svg viewBox="0 0 1 1" onload="evil()"/>',
            ]:
                path.write_text(content)
                with self.assertRaises(PcbAiError):
                    svg_metadata(path)

    def test_engine_scene_hit_and_stale_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = make_project(root / "project")
            state = root / "state"
            state.mkdir()
            board = project.with_suffix(".kicad_pcb")
            board.write_bytes(GEOMETRY)
            engine = Engine([project], state)
            session = next(iter(engine.sessions.entries.values()))
            target = session.target(board.name)
            response = engine.call("hit_test", dict(target, x_mm=10, y_mm=18, layers=["F.Cu"]))
            self.assertTrue(response["ok"], response)
            self.assertEqual(response["items"][0]["reference"], "R1")
            for value in [float("nan"), float("inf"), True]:
                self.assertFalse(engine.call("hit_test", dict(target, x_mm=value, y_mm=18))["ok"])
            board.write_bytes(GEOMETRY + b"\n")
            self.assertEqual(engine.call("scene_pcb", target)["error"]["code"], "stale_revision")
