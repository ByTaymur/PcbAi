import copy
import shutil
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from pcbai.bom.audit import audit, components, check
from pcbai.bom.values import canonical, rating
from pcbai.core.contract import PcbAiError
from pcbai.kicad.files import revision
from pcbai.tools.engine import Engine
from tests.helpers import make_project

FIXTURE = Path(__file__).parent / "fixtures/faults/21-bom-value-case/bom.xml"


class BomAuditTests(unittest.TestCase):
    def test_field_cannot_replace_missing_native_footprint_identity(self):
        tree = ET.fromstring(FIXTURE.read_bytes())
        node = tree.find("components/comp")
        footprint = node.find("footprint")
        ET.SubElement(node.find("fields"), "field", name="Footprint").text = footprint.text
        footprint.text = ""
        with self.assertRaises(PcbAiError):
            audit(ET.tostring(tree))
        footprint.text = "Resistor_SMD:R_0603_1608Metric"
        node.find("fields/field[@name='Footprint']").text = ""
        self.assertEqual(audit(ET.tostring(tree))["missing_field_count"], 0)

    def test_case_variant_fixture_is_one_exact_value_group_without_missing_fields(self):
        result = audit(FIXTURE.read_bytes())
        self.assertEqual(result["missing_field_count"], 0)
        self.assertEqual(result["value_groups"][0]["quantity"], 2)
        self.assertEqual(result["value_groups"][0]["canonical_value"], "10000")
        self.assertEqual([f["rule_id"] for f in result["findings"]], ["bom_value_format_variation"])
        self.assertEqual(result["findings"][0]["source"], "bom")
        self.assertFalse(result["part_identity_verified"])
        self.assertFalse(result["assembly_verified"])

    def test_exact_values_units_and_unknown_notation(self):
        for text in ("10K", "10k", "10kΩ", "10000", "1e4", "10kohm"):
            self.assertEqual(canonical("resistor", text), "10000")
        self.assertEqual(canonical("resistor", "4k7"), "4700")
        self.assertEqual(canonical("resistor", "4R7"), "4.7")
        self.assertEqual(canonical("resistor", "0R"), "0")
        self.assertEqual(canonical("resistor", "1M"), "1000000")
        for text in ("1m", "1Kjunk", "float(10)", "nan", "1e9999", "1e31", "1/10", "10MΩx"):
            self.assertIsNone(canonical("resistor", text))
        for text in ("100n", "100nF", "0.1uF", "0.1µF", "1e-7F"):
            self.assertEqual(canonical("capacitor", text), "0.0000001")
        for text in ("100", "1M", "0F", "-1uF", "1ufjunk", "1fF", "100nfF"):
            self.assertIsNone(canonical("capacitor", text))
        self.assertEqual(rating("± 5%", "tolerance"), "5")
        self.assertEqual(rating("600mV", "voltage"), "0.6")
        self.assertIsNone(rating("5", "tolerance"))

    def test_missing_fields_count_and_jlc_policy_are_explicit(self):
        tree = ET.fromstring(FIXTURE.read_bytes())
        for node in tree.findall("components/comp"):
            node.remove(node.find("fields"))
        result = audit(ET.tostring(tree), "jlcpcb-2l")
        self.assertEqual(result["missing_field_count"], 8)  # Two × MPN/manufacturer/LCSC/tolerance.
        missing = [f for f in result["findings"] if f["rule_id"] == "bom_missing_field"]
        self.assertEqual(len({f["finding_id"] for f in missing}), 8)
        self.assertEqual(result["verified"], "checks_findings")

    def test_capacitor_requirements_and_declared_footprint_conflict(self):
        tree = ET.fromstring(FIXTURE.read_bytes())
        node = tree.find("components/comp")
        node.find("libsource").set("part", "C")
        node.find("value").text = "100n"
        result = audit(ET.tostring(tree))
        rules = [f["rule_id"] for f in result["findings"]]
        self.assertIn("bom_footprint_category_conflict", rules)
        self.assertEqual(result["missing_field_count"], 2)  # voltage + dielectric.

    def test_literal_mpn_alias_conflict_and_intentional_group_metadata_difference(self):
        tree = ET.fromstring(FIXTURE.read_bytes())
        node = tree.find("components/comp")
        ET.SubElement(node.find("fields"), "field", name="Manufacturer Part Number").text = "example-r10k"
        result = audit(ET.tostring(tree))
        self.assertTrue(any(f["rule_id"] == "bom_field_alias_conflict" for f in result["findings"]))
        self.assertEqual(result["missing_field_count"], 0)
        tree = ET.fromstring(FIXTURE.read_bytes())
        tree.findall("components/comp")[1].find("fields/field[@name='Tolerance']").text = "5%"
        result = audit(ET.tostring(tree))
        f = next(f for f in result["findings"] if f["rule_id"] == "bom_group_field_variation")
        self.assertIn("intentional", f["message"])
        self.assertEqual(f["field"], "tolerance")

    def test_entities_duplicate_refs_fields_and_native_identity_are_rejected(self):
        base = ET.fromstring(FIXTURE.read_bytes())
        for mutation in ("ref", "field", "identity"):
            tree = copy.deepcopy(base)
            node = tree.find("components/comp")
            if mutation == "ref":
                tree.findall("components/comp")[1].set("ref", "r1")
            elif mutation == "field":
                ET.SubElement(node.find("fields"), "field", name="mpn").text = "OTHER"
            else:
                ET.SubElement(node, "value").text = "1K"
            with self.assertRaises(PcbAiError):
                components(ET.tostring(tree))
        with self.assertRaises(PcbAiError):
            components(b'<!DOCTYPE export [<!ENTITY x "x">]><export/>')

    def test_unknown_category_or_value_is_incomplete_and_input_is_not_mutated(self):
        tree = ET.fromstring(FIXTURE.read_bytes())
        tree.find("components/comp/libsource").set("lib", "Custom")
        raw = ET.tostring(tree)
        result = audit(raw)
        self.assertEqual(result["verified"], "checks_incomplete")
        self.assertEqual(raw, ET.tostring(tree))
        tree = ET.fromstring(FIXTURE.read_bytes())
        tree.find("components/comp/value").text = "10m"
        self.assertEqual(audit(ET.tostring(tree))["verified"], "checks_incomplete")

    def test_engine_target_and_failed_checks_are_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = make_project(root / "project")
            (root / "state").mkdir()
            engine = Engine([project], root / "state")
            session = engine.call("pcbai_status", {})["sessions"][0]["id"]
            result = engine.call(
                "check_bom_fields",
                dict(
                    session_id=session,
                    document="Test.kicad_sch",
                    revision=revision(project.parent),
                    profile="../wrong",
                ),
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["verified"], "checks_incomplete")

    def test_real_native_copy_counts_and_root_revision_unchanged(self):
        from pcbai.external import find_kicad_cli

        try:
            find_kicad_cli()
        except PcbAiError:
            self.skipTest("KiCad CLI unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            shutil.copytree(Path(__file__).parent / "fixtures/faults/01-drc-zero-short", root)
            before = revision(root)
            result = check(root, "fault.kicad_sch", before)
            self.assertEqual(revision(root), before)
            self.assertEqual(len(result["components"]), 2)
            self.assertEqual(result["missing_field_count"], 6)  # J1/J2 × footprint/MPN/manufacturer.
            self.assertFalse(result["excluded_component_coverage_verified"])
