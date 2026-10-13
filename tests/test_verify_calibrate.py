import copy
import json
import os
import unittest
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.verify.calibrate import calibrate, native_model, normalized_name


def model(nets=None):
    return dict(components=["J1", "J2"], sheet_instances=1, nets=nets if nets is not None else {"/LEFT": [["J1", "1"]], "/RIGHT": [["J2", "1"]]},
                footprints=2, pads=2, vias=0, segments=0)


class CalibrationTests(unittest.TestCase):
    def test_fixture09_name_swap_detected(self):
        external = json.loads((Path(__file__).parent / "fixtures/faults/09-wrong-net-members/reported-net-members.json")
                              .read_text(encoding="utf-8"))
        output = calibrate(model(), dict(model(), nets=external["nets"]))
        self.assertEqual(sum(f["rule_id"] == "net_name_member_swap" for f in output["findings"]), 2)
        self.assertTrue(next(c for c in output["checks_run"] if c["check_id"] == "net_partitions")["matches"])

    def test_missing_member_fails(self):
        external = model()
        external["nets"]["/LEFT"] = []
        output = calibrate(model(), external)
        self.assertIn("net_members_mismatch", [f["rule_id"] for f in output["findings"]])
        self.assertFalse(output["calibrated"])

    def test_multiplicity_only_skips_pin_count_detectors(self):
        external = model()
        external["nets"]["/LEFT"].append(["J1", "1"])
        output = calibrate(model(), external)
        gates = {r["check_id"]: r for r in output["detector_gates"]}
        self.assertEqual(gates["topology"]["status"], "not_applicable")
        self.assertEqual(gates["pin_count_current"]["status"], "skipped")
        self.assertEqual(gates["pin_count_current"]["limit_id"], "L-KH-PIN-MULTIPLICITY")

    def test_unnamed_nets_matched_by_partition_not_name(self):
        a, b = model({"Net-(J1-Pin_1)": [["J1", "1"]]}), model({"__unnamed_7": [["J1", "1"]]})
        self.assertTrue(calibrate(a, b)["calibrated"])

    def test_count_mismatch(self):
        output = calibrate(model(), dict(model(), pads=3))
        self.assertIn("count_mismatch", [f["rule_id"] for f in output["findings"]])

    def test_uuid_scope_alias_normalization_requires_native_mapping(self):
        pages = [dict(tstamps="/root/a", names="/ampli/"), dict(tstamps="/root/b", names="/filter/")]
        self.assertEqual(normalized_name("/a/WRFIFO-", pages), "ampli/WRFIFO-")
        self.assertEqual(normalized_name("/b/CSYNCIN-", pages), "filter/CSYNCIN-")
        self.assertEqual(normalized_name("/unknown/WRFIFO-", pages), "unknown/WRFIFO-")
        ambiguous = pages + [dict(tstamps="/root/a", names="/other/")]
        self.assertEqual(normalized_name("/a/WRFIFO-", ambiguous), "a/WRFIFO-")

    def test_missing_fields_are_incomplete_and_malformed_model_is_rejected(self):
        self.assertEqual(calibrate(model(), dict(nets=model()["nets"]))["verified"], "checks_incomplete")
        with self.assertRaises(PcbAiError):
            calibrate(model(), dict(model(), nets={"bad": ["code"]}))
        self.assertFalse(calibrate(model(), dict(model(), components=[]))["calibrated"])

    def test_native_fixture09_calibration(self):
        from tests.test_fault_fixtures import FaultFixtureTests
        case = FaultFixtureTests()
        case.setUp()
        with case.fixture("09-wrong-net-members") as (_, _, project):
            native = native_model(project, "fault.kicad_sch", "fault.kicad_pcb")
            external = json.loads((project / "reported-net-members.json").read_text(encoding="utf-8"))
            output = calibrate(native, dict(native, nets=external["nets"]))
        self.assertEqual(sum(f["rule_id"] == "net_name_member_swap" for f in output["findings"]), 2)

    def test_model_inputs_not_mutated(self):
        a, b = model(), model()
        original = copy.deepcopy((a, b))
        calibrate(a, b)
        self.assertEqual((a, b), original)

    def test_real_kicad_happy_five_demos(self):
        if not os.environ.get("PCBAI_KICAD_HAPPY"):
            self.skipTest("Configure PCBAI_KICAD_HAPPY for real external model acceptance")
        from pcbai.verify.adapters.kicad_happy import from_reports
        from tests.test_kicad_integration import demo_root
        from pcbai.external import find_kicad_python, run
        import shutil
        import tempfile
        upstream = Path(os.environ["PCBAI_KICAD_HAPPY"]).resolve()
        git = run(["git", "-C", upstream, "rev-parse", "HEAD"], timeout=20)
        self.assertEqual(git.stdout.strip(), "06840467ad0f5d76af45f64449b1f5ecb10f052f")
        demos = demo_root()
        if demos is None:
            self.skipTest("Real KiCad demo corpus required")
        for name in ("ecc83", "pic_programmer", "video", "interf_u", "stickhub"):
            with self.subTest(demo=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                shutil.copytree(demos / name, root / "project")
                project = (root / "project/ecc83-pp.kicad_pro" if name == "ecc83"
                           else next((root / "project").glob("*.kicad_pro")))
                reports = []
                for kind, suffix in (("schematic", ".kicad_sch"), ("pcb", ".kicad_pcb")):
                    script = upstream / f"skills/kicad/scripts/analyze_{kind}.py"
                    output = run([find_kicad_python(), "-I", script, project.with_suffix(suffix)], cwd=root, timeout=120)
                    self.assertEqual(output.returncode, 0, output.stderr)
                    reports.append(json.loads(output.stdout))
                native = native_model(project.parent, project.with_suffix(".kicad_sch").name,
                                      project.with_suffix(".kicad_pcb").name)
                calibrated = calibrate(native, from_reports(*reports))
                for control in calibrated["checks_run"]:
                    if control["check_id"] not in {"net_names", "net_multiplicity"}:
                        self.assertEqual(control["status"], "ran", control)
                        self.assertTrue(control["matches"], control)
                self.assertTrue(next(c for c in calibrated["checks_run"] if c["check_id"] == "net_partitions")["matches"])
                # Different chosen aliases are reported, never inferred equal from matching members.
                names_match = next(c for c in calibrated["checks_run"] if c["check_id"] == "net_names")["matches"]
                self.assertEqual(names_match, name not in {"pic_programmer", "video"})
                if not names_match:
                    self.assertEqual(calibrated["detector_gates"][0]["status"], "skipped")
                self.assertEqual(sum(f["rule_id"] == "pin_multiplicity" for f in calibrated["findings"]),
                                 19 if name == "pic_programmer" else 0)
