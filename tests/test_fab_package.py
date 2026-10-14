import csv
import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from pcbai.core.contract import PcbAiError
from pcbai.kicad.exports import export_fab, gerber_layer
from pcbai.kicad.files import revision
from tests.helpers import make_project
from tests.test_kicad_integration import demo_root

FUNCTIONS = {"F.Cu": "Copper,L1,Top", "B.Cu": "Copper,L2,Bot", "F.Mask": "Soldermask,Top",
             "B.Mask": "Soldermask,Bot", "F.Silkscreen": "Legend,Top", "B.Silkscreen": "Legend,Bot",
             "Edge.Cuts": "Profile,NP", "F.Paste": "Paste,Top", "B.Paste": "Paste,Bot"}
STATS = dict(board=dict(has_outline=True, width="10 mm", height="20 mm"), components=dict(total=dict(total=1)))


class FabPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = make_project(self.root / "project")
        self.project.with_suffix(".kicad_pcb").write_bytes(b'(kicad_pcb (layers (0 "F.Cu" signal "top_cu") (2 "B.Cu" signal "bottom_cu") (4 "F.Mask" user) (5 "B.Mask" user) (6 "F.Silkscreen" user) (7 "B.Silkscreen" user) (8 "Edge.Cuts" user) (9 "F.Paste" user) (10 "B.Paste" user)))')
        self.revision = revision(self.project.parent)
        self.destination = self.root / "fabrication.zip"
        self.calls = []

    def fake(self, argv, _cwd):
        self.calls.append(argv)
        path = Path(argv[argv.index("--output") + 1])
        operation = argv[3]
        if operation == "gerbers":
            for layer, function in FUNCTIONS.items():
                if layer.endswith("Paste") and "F.Paste" not in argv[argv.index("--layers") + 1]:
                    continue
                name = "top_cu" if layer == "F.Cu" else "bottom_cu" if layer == "B.Cu" else layer.replace(".", "_")
                (path / ("Test-" + name + ".gbr")).write_text(f"%TF.FileFunction,{function}*%\n%MOMM*%\nM02*\n")
            (path / "Test-job.gbrjob").write_text('{}')
        elif operation == "drill":
            (path / "Test.drl").write_text("M48\nMETRIC\n%\nM30\n")
        elif operation == "ipcd356":
            path.write_text("P  UNITS CUST 0\n999\n")
        elif operation == "stats":
            path.write_text(json.dumps(STATS))
        elif operation == "pos":
            path.write_text("Ref,Val,Package,PosX,PosY,Rot,Side\n" +
                            ("R1,10k,R_0603,1,2,90,top\n" if argv[argv.index("--side") + 1] == "front" else ""))

    def export(self, *, assembly=False, fake=None):
        with patch("pcbai.kicad.exports.find_kicad_cli", return_value="configured-cli"), \
                patch("pcbai.kicad.exports.command", side_effect=fake or self.fake):
            return export_fab(self.project.parent, "Test.kicad_pcb", self.destination, self.revision, assembly=assembly)

    def test_complete_roles_hashes_and_assembly_layers_with_aliased_copper(self):
        report = self.export(assembly=True)
        self.assertFalse(report["production_verified"])
        self.assertEqual({r["layer"] for r in report["files"] if "layer" in r}, set(FUNCTIONS))
        self.assertTrue({"ipc_d356", "position_front_raw", "position_back_raw", "board_statistics", "gerber_job", "drill"}
                        <= {r["role"] for r in report["files"]})
        with zipfile.ZipFile(self.destination) as archive:
            self.assertEqual(json.loads(archive.read("manifest.json")), report)
            for entry in report["files"]:
                self.assertEqual(hashlib.sha256(archive.read(entry["name"])).hexdigest(), entry["sha256"])
        self.assertEqual(revision(self.project.parent), self.revision)

    def test_no_assembly_has_no_paste_and_positions_use_matching_absolute_policy(self):
        report = self.export()
        self.assertFalse(any(r.get("layer", "").endswith("Paste") for r in report["files"]))
        self.assertEqual(report["coordinate_origin"], "absolute")
        for argv in self.calls:
            self.assertNotIn("--use-drill-file-origin", argv)
            self.assertNotIn("--bottom-negate-x", argv)
        drill = next(argv for argv in self.calls if argv[3] == "drill")
        self.assertEqual(drill[drill.index("--drill-origin") + 1], "absolute")

    def test_profile_check_and_export_share_tightened_copy(self):
        seen = []

        def check_copy(root, document, expected_revision, profile):
            project = root / "Test.kicad_pro"
            project.write_text(json.dumps(dict(board=dict(design_settings=dict(rules=dict(min_track_width=.6))))))
            return dict(clean=True, checked_revision=revision(root), original_revision=expected_revision)

        def fake(argv, cwd):
            seen.append(json.loads((cwd / "Test.kicad_pro").read_text())["board"]["design_settings"]["rules"]["min_track_width"])
            self.assertEqual(revision(cwd), report_holder["checked_revision"])
            self.fake(argv, cwd)

        report_holder = {}

        def captured_check(*args):
            output = check_copy(*args)
            report_holder.update(output)
            return output

        with patch("pcbai.fab.profile.check_copy", side_effect=captured_check), \
                patch("pcbai.kicad.exports.find_kicad_cli", return_value="configured-cli"), \
                patch("pcbai.kicad.exports.command", side_effect=fake):
            output = export_fab(self.project.parent, "Test.kicad_pcb", self.destination, self.revision, profile="generic")
        self.assertEqual(seen, [.6] * 6)
        self.assertEqual(output["profile_check"]["checked_revision"], report_holder["checked_revision"])
        self.assertEqual(revision(self.project.parent), self.revision)

    def test_disabled_silk_is_explicitly_omitted_not_required_as_enabled(self):
        source = self.project.with_suffix(".kicad_pcb")
        source.write_bytes(source.read_bytes().replace(b'(7 "B.Silkscreen" user)', b''))
        self.revision = revision(self.project.parent)
        def fake(argv, cwd):
            self.fake(argv, cwd)
            if argv[3] == "gerbers":
                output = Path(argv[argv.index("--output") + 1])
                (output / "Test-B_Silkscreen.gbr").unlink()
        output = self.export(fake=fake)
        self.assertIn("B.Silkscreen", output["omitted_disabled_layers"])
        self.assertFalse(output["production_verified"])

    def test_missing_enabled_mask_is_still_rejected(self):
        def fake(argv, cwd):
            self.fake(argv, cwd)
            if argv[3] == "gerbers":
                Path(argv[argv.index("--output") + 1], "Test-B_Mask.gbr").unlink()
        with self.assertRaises(PcbAiError):
            self.export(fake=fake)

    def test_omitted_native_outputs_and_corrupt_positions_fail_without_zip(self):
        for failed in ("ipcd356", "pos", "stats"):
            def fake(argv, cwd, failed=failed):
                if argv[3] != failed:
                    self.fake(argv, cwd)
            with self.subTest(failed=failed), self.assertRaises(PcbAiError):
                self.export(fake=fake)
            self.assertFalse(self.destination.exists())
        def bad(argv, cwd):
            self.fake(argv, cwd)
            if argv[3] == "pos":
                Path(argv[argv.index("--output") + 1]).write_text("Ref,Val,Package,PosX,PosY,Rot,Side\nR1,x,x,nan,2,0,top\n")
        with self.assertRaises(PcbAiError):
            self.export(fake=bad)
        self.assertFalse(self.destination.exists())

    def test_missing_requested_layer_and_bad_ipc_terminator_fail(self):
        def missing(argv, cwd):
            self.fake(argv, cwd)
            if argv[3] == "gerbers":
                Path(argv[argv.index("--output") + 1], "Test-bottom_cu.gbr").unlink()
        with self.assertRaises(PcbAiError):
            self.export(fake=missing)
        def bad(argv, cwd):
            self.fake(argv, cwd)
            if argv[3] == "ipcd356":
                Path(argv[argv.index("--output") + 1]).write_text("truncated")
        with self.assertRaises(PcbAiError):
            self.export(fake=bad)

    def test_gerber_authority_rejects_missing_duplicate_or_wrong_stack(self):
        path = self.root / "board.gbr"
        for header in ("M02*", "%TF.FileFunction,Copper,L3,Inr*%%MOMM*%", "%TF.FileFunction,Copper,L1,Bot*%%MOMM*%",
                       "%TF.FileFunction,Profile,NP*%%TF.FileFunction,Profile,NP*%%MOMM*%",
                       "%TF.FileFunction,Profile,NP*%%MOIN*%"):
            path.write_text(header)
            with self.assertRaises(PcbAiError):
                gerber_layer(path, ["F.Cu", "B.Cu"])


@unittest.skipUnless(demo_root(), "Installed KiCad demo corpus required")
class RealFabPackageTests(unittest.TestCase):
    def test_position_exclusion_flag_and_nonzero_aux_origin_are_explicit(self):
        from pcbai.sexpr import Document
        from pcbai.sch.model import footprints
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(demo_root() / "ecc83", root / "project")
            board = root / "project/ecc83-pp.kicad_pcb"
            data = board.read_bytes()
            doc = Document(data)
            excluded = footprints(data)[0]["Reference"]
            footprint = doc.root.all("footprint")[0]
            attr = footprint.child("attr")
            at = attr.end - 1 if attr else footprint.end - 1
            data = data[:at] + (b" exclude_from_pos_files" if attr else b" (attr exclude_from_pos_files)") + data[at:]
            doc = Document(data)
            setup = doc.root.child("setup")
            axis = setup.child("aux_axis_origin")
            if axis:
                data = data[:axis.start] + b"(aux_axis_origin 100 200)" + data[axis.end:]
            else:
                data = data[:setup.end - 1] + b" (aux_axis_origin 100 200)" + data[setup.end - 1:]
            board.write_bytes(data)
            expected = {p["Reference"]: p["at"] for p in footprints(data)}
            output = root / "fab.zip"
            report = export_fab(board.parent, board.name, output, revision(board.parent), assembly=True)
            self.assertEqual(report["position_policy"], "native_eligible_footprints_unmirrored")
            self.assertTrue(report["position_filters"]["native_exclusion_flags_respected"])
            with zipfile.ZipFile(output) as archive:
                rows = [row for side in ("front", "back") for row in csv.DictReader(
                    archive.read(f"positions-{side}.csv").decode().splitlines())]
            self.assertNotIn(excluded, {row["Ref"] for row in rows})
            self.assertTrue(rows)
            for row in rows:
                self.assertAlmostEqual(float(row["PosX"]), expected[row["Ref"]][0], places=4)
                self.assertAlmostEqual(float(row["PosY"]), -expected[row["Ref"]][1], places=4)

    def test_five_demos_native_package_byte_preservation_and_paste_policy(self):
        for name in ("ecc83", "pic_programmer", "video", "interf_u", "stickhub"):
            with self.subTest(demo=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                shutil.copytree(demo_root() / name, root / "project")
                project = (root / "project/ecc83-pp.kicad_pro" if name == "ecc83" else
                           next((root / "project").glob("*.kicad_pro")))
                board = project.with_suffix(".kicad_pcb")
                initial = revision(project.parent)
                for assembly in (False, True):
                    output = root / f"fabrication-{assembly}.zip"
                    report = export_fab(project.parent, board.name, output, initial, assembly=assembly)
                    self.assertEqual(revision(project.parent), initial)
                    self.assertFalse(report["production_verified"])
                    paste = {r.get("layer") for r in report["files"] if r.get("layer", "").endswith("Paste")}
                    self.assertEqual(paste, {"F.Paste", "B.Paste"} if assembly else set())
                    with zipfile.ZipFile(output) as archive:
                        for entry in report["files"]:
                            self.assertEqual(hashlib.sha256(archive.read(entry["name"])).hexdigest(), entry["sha256"])
                        stats = json.loads(archive.read("board-stats.json"))
                        self.assertGreaterEqual(stats["components"]["total"]["total"], 1)
                        self.assertIn(b"999", archive.read("nets.d356"))
                        for side in ("front", "back"):
                            rows = list(csv.DictReader(archive.read(f"positions-{side}.csv").decode().splitlines()))
                            self.assertTrue(all(row["Side"] == ("top" if side == "front" else "bottom") for row in rows))
