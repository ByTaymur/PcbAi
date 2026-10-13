import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
import hashlib
import json
import zipfile
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli, run
from pcbai.kicad.cli import rule_check
from pcbai.kicad.files import assert_closed
from pcbai.sch.model import edit_value, symbols
from pcbai.sexpr import Document
from pcbai.tools.engine import Engine


def demo_root():
    try:
        cli = Path(find_kicad_cli())
    except PcbAiError:
        return None
    candidates = [cli.parent.parent / "share/kicad/demos", Path("/usr/share/kicad/demos")]
    return next((p for p in candidates if p.is_dir()), None)


@unittest.skipUnless(demo_root(), "Installed KiCad demo corpus required")
class KiCadIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demos = demo_root()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pcbai-integration-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project_root = self.root / "project"
        source = self.demos / "ecc83"
        shutil.copytree(source, self.project_root)
        projects = list(self.project_root.glob("*.kicad_pro"))
        if not projects:
            self.skipTest("ecc83 KiCad project unavailable")
        self.project = projects[0]
        state = self.root / "state"
        state.mkdir()
        self.engine = Engine([self.project], state)
        self.session = next(iter(self.engine.sessions.entries))

    def test_entire_installed_corpus_byte_roundtrip(self):
        paths = [p for p in self.demos.rglob("*") if p.suffix in {".kicad_sch", ".kicad_pcb", ".kicad_sym"}]
        self.assertGreater(len(paths), 10)
        rejected = []
        for path in paths:
            with self.subTest(path=str(path.relative_to(self.demos))):
                data = path.read_bytes()
                relative = path.relative_to(self.demos).as_posix()
                if relative == "royalblue54L_feather/RoyalBlue54L-Feather.kicad_pcb":
                    # This installed demo has unbalanced parentheses; KiCad's own parser tolerates it.
                    # Keep a strict failure instead of certifying a partly parsed board.
                    with self.assertRaises(PcbAiError):
                        Document(data)
                    copied = self.root / "corrupt-demo.kicad_pcb"
                    copied.write_bytes(data)
                    output = run([find_kicad_cli(), "pcb", "drc", str(copied), "--format", "json",
                                  "--output", str(self.root / "corrupt-report.json")])
                    self.assertEqual(output.returncode, 0)
                    rejected.append(relative)
                else:
                    self.assertEqual(Document(data).serialize(), data)
                    if path.suffix == ".kicad_sch":
                        # Include valid unnamed-project instance records from real demos.
                        self.assertIsInstance(symbols(data), list)
        print(f"KiCad corpus: {len(paths) - len(rejected)} byte-identical, {len(rejected)} strict syntax rejection")

    def test_real_erc_and_drc_produce_measured_reports(self):
        for kind, suffix in [("erc", ".kicad_sch"), ("drc", ".kicad_pcb")]:
            documents = list(self.project_root.glob("*" + suffix))
            self.assertTrue(documents)
            document = documents[0].name
            output = self.engine.call(kind, {"session": self.session, "document": document})
            self.assertTrue(output["ok"], output)
            self.assertIn(output["verified"], {kind + "_ok", kind + "_findings"})
            self.assertEqual(len(output["measurements"]), 2)
            self.assertTrue(output["evidence_id"].startswith("ev-"))
            print(output["summary"])

    def test_real_edit_and_restore_preserve_all_other_bytes(self):
        self.require_closed_editors()
        sheet = next(self.project_root.glob("*.kicad_sch"))
        original = sheet.read_bytes()
        reference = next(s["Reference"] for s in symbols(original) if s["Reference"].startswith("R"))
        target = self.engine.sessions.get(self.session).target(sheet.name)
        preview = self.engine.call("set_value", dict(target, mode="preview", reference=reference, value="4k7"))
        self.assertTrue(preview["ok"], preview)
        edited = self.engine.call("set_value", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        self.assertTrue(edited["ok"], edited)
        self.assertTrue(edited["changed"], edited)
        self.assertNotEqual(edited["verified"], "verification_failed", edited)
        self.assertNotEqual(sheet.read_bytes(), original)
        checkpoint = edited["checkpoint"]["id"]
        restore = self.engine.call("restore_checkpoint", dict(edited["target"], mode="preview", checkpoint_id=checkpoint))
        restored = self.engine.call("restore_checkpoint", dict(edited["target"], mode="apply", candidate_id=restore["candidate_id"]))
        self.assertTrue(restored["ok"], restored)
        self.assertEqual(sheet.read_bytes(), original)

    def test_broken_schematic_cannot_be_certified(self):
        sheet = next(self.project_root.glob("*.kicad_sch"))
        sheet.write_bytes(b"(kicad_sch BROKEN")
        with self.assertRaises(PcbAiError):
            rule_check(self.project_root, sheet.name, "erc")

    def test_pdf_export_creates_real_artifact(self):
        sheet = next(self.project_root.glob("*.kicad_sch"))
        output = self.engine.call("schematic_pdf", {"session": self.session, "document": sheet.name})
        self.assertTrue(output["ok"], output)
        self.assertTrue(Path(output["path"]).read_bytes().startswith(b"%PDF"))

    def test_shared_hierarchy_edit_netlist_and_restore(self):
        self.require_closed_editors()
        folder = self.root / "hierarchy"
        source = self.demos / "complex_hierarchy"
        if not source.is_dir():
            self.skipTest("complex_hierarchy demo unavailable")
        shutil.copytree(source, folder)
        project = folder / "complex_hierarchy.kicad_pro"
        engine = Engine([project], self.engine.state)
        session = next(iter(engine.sessions.entries))
        sheet = folder / "ampli_ht.kicad_sch"
        original = sheet.read_bytes()
        target = engine.sessions.get(session).target(sheet.name)
        listed = engine.call("list_symbols", {"session": session, "document": sheet.name})
        self.assertTrue(listed["ok"], listed)
        resistor = [s for s in listed["symbols"] if s["Reference"] in {"R203", "R303"}]
        self.assertEqual(len(resistor), 2)
        self.assertEqual({s["Value"] for s in resistor}, {"22K"})
        previews = [engine.call("set_value", dict(target, mode="preview", reference=ref, value="47k"))
                    for ref in ["R203", "R303"]]
        for preview in previews:
            self.assertTrue(preview["ok"], preview)
            self.assertEqual(preview["affected_references"], ["R203", "R303"])
            self.assertEqual(len(preview["affected_instances"]), 2)
            self.assertTrue(preview["warnings"])
        self.assertEqual(previews[0]["after_sha256"], previews[1]["after_sha256"])
        edited = engine.call("set_value", dict(target, mode="apply", candidate_id=previews[1]["candidate_id"]))
        self.assertTrue(edited["changed"], edited)
        self.assertNotEqual(edited["verified"], "verification_failed", edited)
        expected, _ = edit_value(original, "R303", "47k", project.stem)
        self.assertEqual(sheet.read_bytes(), expected)
        netlist = self.root / "hierarchy.xml"
        export_folder = self.root / "netlist-copy"
        shutil.copytree(folder, export_folder)
        output = run([find_kicad_cli(), "sch", "export", "netlist", "--format", "kicadxml",
                      "--output", str(netlist), str(export_folder / project.with_suffix(".kicad_sch").name)])
        self.assertEqual(output.returncode, 0, output.stderr)
        components = {c.attrib["ref"]: c.findtext("value") for c in ET.parse(netlist).findall("./components/comp")}
        self.assertEqual([components[r] for r in ["R203", "R303"]], ["47k", "47k"])
        restore = engine.call("restore_checkpoint", dict(edited["target"], mode="preview",
                              checkpoint_id=edited["checkpoint"]["id"]))
        self.assertTrue(restore["ok"], restore)
        restored = engine.call("restore_checkpoint", dict(edited["target"], mode="apply",
                               candidate_id=restore["candidate_id"]))
        self.assertTrue(restored["changed"], restored)
        self.assertEqual(sheet.read_bytes(), original)
        self.assertFalse((folder / ".pcbai-write.lock").exists())
        print("Shared hierarchy: R203/R303 = 47k in real KiCad netlist; restore byte-identical")

    def require_closed_editors(self):
        try:
            assert_closed(self.project_root)
        except PcbAiError as exc:
            if exc.code == "editor_open":
                self.skipTest("Real file edits require closed KiCad editors, including the project manager")
            raise

    def test_real_board_stats_match_saved_footprint_count(self):
        board = next(self.project_root.glob("*.kicad_pcb"))
        target = self.engine.sessions.get(self.session).target(board.name)
        output = self.engine.call("board_stats", target)
        self.assertTrue(output["ok"], output)
        saved = self.engine.call("list_footprints", dict(session=self.session, document=board.name))
        self.assertEqual(output["statistics"]["components"]["total"]["total"], len(saved["footprints"]))
        self.assertEqual(output["measurements"][0]["unit"], "mm")
        self.assertEqual(output["target"], target)
        print("Real PCB dimensions:", output["statistics"]["board"]["width"], output["statistics"]["board"]["height"])

    def test_real_svg_matrix_matches_independent_kicad_pad_centres(self):
        import math
        from pcbai.view_render import apply_matrix, svg_metadata
        board = self.project.with_suffix(".kicad_pcb")
        target = self.engine.sessions.get(self.session).target(board.name)
        scene = self.engine.call("scene_pcb", target)
        rendered = self.engine.call("render_pcb", dict(target, layers=["F.Cu", "B.Cu", "Edge.Cuts"]))
        self.assertTrue(rendered["ok"], rendered)
        render = rendered["render"]
        circles = []
        for layer in render["layers"][:2]:
            svg, _ = svg_metadata(layer["path"])
            circles.extend([[float(n.get("cx")), float(n.get("cy"))] for n in svg.iter()
                            if n.tag.split("}")[-1] == "circle"])
        pads = [p for p in scene["scene"]["items"] if p["type"] == "pad" and p["shape"] == "circle"]
        self.assertGreater(len(pads), 3)
        for pad in pads:
            expected = apply_matrix(render["mm_to_svg"], pad["at"])
            observed = min(circles, key=lambda p: math.dist(expected, p))
            self.assertLess(math.dist(apply_matrix(render["svg_to_mm"], observed), pad["at"]), .05)
        # Same revision reuses artifacts, and source files remain unchanged.
        cached = self.engine.call("render_pcb", dict(target, layers=["F.Cu", "B.Cu", "Edge.Cuts"]))
        self.assertEqual(cached["render"], render)
        self.assertEqual(self.engine.sessions.get(self.session).target(board.name), target)

    def test_real_schematic_marker_value_edit_and_status(self):
        self.require_closed_editors()
        sheet = self.project.with_suffix(".kicad_sch")
        original = sheet.read_bytes()
        symbol = next(s for s in symbols(original) if s["Reference"].startswith("R"))
        target = self.engine.sessions.get(self.session).target(sheet.name)
        current = self.engine.call("get_markers", {"session": self.session})
        marker_preview = self.engine.call("set_marker", dict(target, mode="preview", markers_revision=current["markers_revision"],
            marker=dict(kind="point", space="sch", points_mm=[symbol["at"][:2]], note="Set this resistor to 4k7")), source="view")
        self.assertTrue(marker_preview["ok"], marker_preview)
        marker_saved = self.engine.call("set_marker", dict(target, mode="apply", candidate_id=marker_preview["candidate_id"],
            markers_revision=marker_preview["markers_revision"]), source="view")
        self.assertTrue(marker_saved["ok"], marker_saved)
        preview = self.engine.call("set_value", dict(target, mode="preview", reference=symbol["Reference"], value="4k7"))
        self.assertTrue(preview["ok"], preview)
        applied = self.engine.call("set_value", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        self.assertTrue(applied["ok"], applied)
        self.assertTrue(applied["changed"], applied)
        status = self.engine.call("update_marker_status", dict(applied["target"], mode="preview", n=1, status="done",
            reason="Value changed with a checkpoint", evidence_id=applied["change_id"], markers_revision=marker_saved["markers_revision"]))
        self.assertTrue(status["ok"], status)
        done = self.engine.call("update_marker_status", dict(applied["target"], mode="apply", candidate_id=status["candidate_id"],
            markers_revision=status["markers_revision"]))
        self.assertTrue(done["ok"], done)
        self.assertEqual(self.engine.call("get_markers", {"session": self.session})["markers"][0]["status"], "done")

    def test_real_svg_rotated_front_and_back_pad_coordinates(self):
        import math
        from pcbai.view_render import apply_matrix, svg_metadata
        from tests.test_views import GEOMETRY
        path = self.project.with_suffix(".kicad_pcb")
        path.write_bytes(GEOMETRY.replace(b'(kicad_pcb ', b'(kicad_pcb (version 20241229) (generator "pcbnew") ')
                         .replace(b'smd rect', b'smd circle').replace(b'(size 1 2)', b'(size 1 1)'))
        target = self.engine.sessions.get(self.session).target(path.name)
        rendered = self.engine.call("render_pcb", dict(target, layers=["F.Cu", "B.Cu", "Edge.Cuts"]))
        self.assertTrue(rendered["ok"], rendered)
        scene = self.engine.call("scene_pcb", target)["scene"]
        for layer, uuid in [("F.Cu", "p1"), ("B.Cu", "p2")]:
            artifact = next(i for i in rendered["render"]["layers"] if i["name"] == layer)
            svg, _ = svg_metadata(artifact["path"])
            circles = [[float(n.get("cx")), float(n.get("cy"))] for n in svg.iter() if n.tag.split("}")[-1] == "circle"]
            pad = next(i for i in scene["items"] if i["uuid"] == uuid)
            expected = apply_matrix(rendered["render"]["mm_to_svg"], pad["at"])
            self.assertTrue(circles)
            self.assertLess(min(math.dist(c, expected) for c in circles), .05)

    def test_real_render_and_fab_leave_source_revision_unchanged(self):
        board = next(self.project_root.glob("*.kicad_pcb"))
        target = self.engine.sessions.get(self.session).target(board.name)
        rendered = self.engine.call("render_board", dict(target, width=320, height=240))
        self.assertTrue(rendered["ok"], rendered)
        self.assertTrue(Path(rendered["path"]).read_bytes().startswith(b"\x89PNG"))
        output = self.engine.call("export_fab", target)
        self.assertTrue(output["ok"], output)
        self.assertEqual(output["verified"], "not_run")
        self.assertTrue(output["warnings"])
        with zipfile.ZipFile(output["path"]) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["revision"], target["revision"])
            self.assertFalse(manifest["production_verified"])
            for entry in manifest["files"]:
                self.assertEqual(hashlib.sha256(archive.read(entry["name"])).hexdigest(), entry["sha256"])
            # Copper output filenames can use board-specific layer names such as
            # top_cu/bottom_cu. Verify the Gerber X2 function, not a guessed name.
            gerbers = "\n".join(archive.read(name).decode("utf-8", errors="replace")
                                for name in archive.namelist() if name.endswith(".gbr"))
            for function in ["TF.FileFunction,Copper,L1,Top", "TF.FileFunction,Copper,L2,Bot", "TF.FileFunction,Profile"]:
                self.assertIn(function, gerbers)
            self.assertTrue(any(name.endswith(".drl") for name in archive.namelist()))
        self.assertEqual(self.engine.sessions.get(self.session).target(board.name), target)
        print("Real PNG and Gerber/drill ZIP generated; source revision unchanged")
