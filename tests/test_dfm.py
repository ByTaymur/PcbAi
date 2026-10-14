import copy
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.fab.dfm import RULES, calibrate, canonical_view, normalize
from pcbai.fab.drill import parse as parse_drill
from pcbai.fab.profile import load
from pcbai.kicad.files import digest
from pcbai.verify.manifest import verification

DRILL = b'M48\n; FORMAT={-:-/ absolute / metric / decimal}\nFMAT,2\nMETRIC\nT1C0.6\n%\nG90\nG05\nT1\nX1.0Y2.0\nX3.0Y4.0G85X5.0Y4.0\nG05\nM30\n'


def report(profile=None):
    profile = profile or load("generic")
    grouped = {}
    for identifier in profile["dfm_required_checks"]:
        category = RULES["checks"][identifier]
        grouped.setdefault(category, []).append(dict(check_id=identifier, category_id=category, status="pass",
                                                     violations=[], confidence="high", metric=dict(measured_value=1.0)))
    return dict(schema_version="1.0.0", ruleset=dict(name=profile["dfm_ruleset_id"]),
                run=dict(tool="pcb-dfm", tool_version="1.0.0"), summary=dict(geometry_source="gerber", overall_score=100),
                categories=[dict(category_id=key, checks=value) for key, value in grouped.items()])


class DfmContractTests(unittest.TestCase):
    def test_pass_without_required_measurement_is_incomplete(self):
        raw = report()
        row = raw["categories"][0]["checks"][0]
        row["metric"]["measured_value"] = None
        findings, checks = normalize(raw, load("generic"))
        self.assertEqual(verification(checks, findings), "checks_incomplete")
        self.assertTrue(any(check["reason"] == "required_geometry_unmeasured" for check in checks))

    def test_score_and_exit_cannot_replace_required_check_coverage(self):
        profile = load("generic")
        raw = report(profile)
        findings, checks = normalize(raw, profile)
        self.assertEqual(verification(checks, findings), "checks_ok")
        raw["categories"][0]["checks"][0]["status"] = "not_applicable"
        findings, checks = normalize(raw, profile)
        self.assertEqual(verification(checks, findings), "checks_incomplete")
        raw = report(profile)
        raw["categories"][0]["checks"].pop()
        findings, checks = normalize(raw, profile)
        self.assertEqual(verification(checks, findings), "checks_incomplete")

    def test_unknown_duplicate_schema_and_status_are_invalid(self):
        for mutation in (lambda raw: raw.update(schema_version="2.0"),
                         lambda raw: raw["categories"][0]["checks"][0].update(status="unknown"),
                         lambda raw: raw["categories"][0]["checks"].append(copy.deepcopy(raw["categories"][0]["checks"][0])),
                         lambda raw: raw["categories"][0]["checks"][0].update(check_id="invented"),
                         lambda raw: raw["summary"].update(geometry_source="kicad-native"),
                         lambda raw: raw["run"].update(tool="unknown")):
            raw = report()
            mutation(raw)
            with self.assertRaises(PcbAiError):
                normalize(raw, load("generic"))

    def test_crash_is_failed_coverage_high_is_not_deterministic_and_empty_fail_is_visible(self):
        raw = report()
        row = raw["categories"][0]["checks"][0]
        row.update(status="fail", violations=[dict(message="Check crashed: ValueError: bad input", severity="error")])
        findings, checks = normalize(raw, load("generic"))
        self.assertEqual(verification(checks, findings), "checks_incomplete")
        self.assertEqual(findings[0]["confidence"], "heuristic")
        self.assertEqual(findings[0]["external_confidence"], "high")
        row["violations"] = []
        findings, checks = normalize(raw, load("generic"))
        self.assertEqual(verification(checks, findings), "checks_findings")
        self.assertEqual(findings[0]["severity"], "error")

    def test_native_calibration_mismatch_and_missing_fields_never_clean(self):
        manifest = dict(files=[dict(layer=layer) for layer in ("F.Cu", "B.Cu", "F.Mask", "B.Mask")])
        stats = dict(board=dict(width="10 mm", height="20 mm"))
        calibration = dict(schema_version=1, geometry_source="gerber", copper_files=["pcbai-F_Cu.gbr", "pcbai-B_Cu.gbr"],
                           mask_files=["pcbai-F_Mask.gbr", "pcbai-B_Mask.gbr"],
                           drill_hits=3, drill_slots=1, outline_bounds_kind="linear_centreline",
                           outline_bounds=dict(width_mm=10, height_mm=20))
        findings, checks = calibrate(calibration, manifest, stats, 3, 1)
        self.assertEqual(verification(checks, findings), "checks_ok")
        calibration["copper_files"] = []
        findings, checks = calibrate(calibration, manifest, stats, 3, 1)
        self.assertEqual(verification(checks, findings), "checks_findings")
        self.assertEqual(findings[0]["source"], "calibration")
        findings, checks = calibrate(None, manifest, stats, 3, 1)
        self.assertEqual(verification(checks, findings), "checks_incomplete")
        calibration.update(copper_files=["pcbai-F_Cu.gbr", "pcbai-B_Cu.gbr"], outline_bounds_kind="unavailable_or_curved")
        findings, checks = calibrate(calibration, manifest, stats, 3, 1)
        self.assertEqual(verification(checks, findings), "checks_incomplete")
        calibration.update(outline_bounds_kind="linear_centreline", mask_files=[])
        findings, checks = calibrate(calibration, manifest, stats, 3, 1)
        self.assertEqual(verification(checks, findings), "checks_findings")

    def test_filename_view_preserves_each_artwork_byte_and_checks_original_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = b'%TF.FileFunction,Copper,L1,Top*%%MOMM*%M02*'
            manifest = dict(files=[dict(name="French-Comp.gbr", role="gerber", layer="F.Cu", sha256=digest(raw))])
            with zipfile.ZipFile(root/"native.zip", "w") as archive:
                archive.writestr("French-Comp.gbr", raw)
                archive.writestr("manifest.json", json.dumps(manifest))
            mapping = canonical_view(root/"native.zip", root/"view.zip", manifest)
            with zipfile.ZipFile(root/"view.zip") as archive:
                self.assertEqual(archive.read("pcbai-F_Cu.gbr"), raw)
            self.assertEqual(mapping[0]["sha256"], digest(raw))
            manifest["files"][0]["sha256"] = "bad"
            with self.assertRaises(PcbAiError):
                canonical_view(root/"native.zip", root/"bad.zip", manifest)


class DrillSubsetTests(unittest.TestCase):
    def test_hits_and_g85_slots_are_counted_separately(self):
        parsed = parse_drill(DRILL)
        self.assertEqual(len(parsed["hits"]), 1)
        self.assertEqual(len(parsed["slots"]), 1)
        self.assertFalse(parsed["plating_verified"])

    def test_unknown_incremental_units_or_truncated_drill_is_rejected(self):
        for raw in (DRILL.replace(b'G90', b'G91'), DRILL.replace(b'METRIC', b'INCH'),
                    DRILL.replace(b'M30', b''), DRILL+b'X1Y1\n', DRILL.replace(b'T1\nX', b'T99\nX'),
                    DRILL.replace(b'M48', b'M48\nM48'), DRILL.replace(b'X1.0Y2.0', b'R3X1.0Y2.0')):
            with self.assertRaises(PcbAiError):
                parse_drill(raw)


@unittest.skipUnless(os.environ.get("PCBAI_PCB_DFM_PYTHON"), "Configured separate pcb-dfm Python required")
class NativeDfmTests(unittest.TestCase):
    def test_real_owned_native_fixture_separate_worker_and_calibration(self):
        import shutil
        from pcbai.fab.dfm import check
        from pcbai.kicad.files import revision
        with tempfile.TemporaryDirectory(prefix="pcbai-dfm-native-") as temporary:
            root = Path(temporary)/"project"
            shutil.copytree(Path(__file__).parent/"fixtures/faults/01-drc-zero-short", root)
            before = revision(root)
            output = check(root, "fault.kicad_pcb", before)
            self.assertEqual(revision(root), before)
            self.assertFalse(output["production_verified"])
            self.assertEqual(output["calibration"]["drill_hits"], 0)
            self.assertEqual(output["calibration"]["drill_slots"], 0)
            self.assertEqual(set(output["calibration"]["copper_files"]), {"pcbai-F_Cu.gbr", "pcbai-B_Cu.gbr"})
            self.assertTrue(all(row["status"] == "ran" for row in output["checks_run"] if row["check_id"].startswith("dfm_calibration:")))
            self.assertNotEqual(output["verified"], "checks_ok")  # Obligatory missing drill/mask features remain incomplete.
