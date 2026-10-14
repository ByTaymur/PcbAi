import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from pcbai.core.contract import PcbAiError
from pcbai.pcb.engine_metrics import added_errors, finding_key
from pcbai.tools.engine import Engine
from pcbai.verify.findings import SCHEMA, normalize_findings
from tests import test_route_engines
from tests.helpers import make_project
from tests.test_fault_fixtures import source_hashes
from tests.test_kicad_integration import demo_root


def finding(*, rule="clearance", uuid="pad-1", x=1.25, y=2.5, severity="error", **extra):
    return dict(type=rule, severity=severity, description="Native description", group="violations",
                items=[dict(uuid=uuid, pos=dict(x=x, y=y), description="Native item")], **extra)


def old_key(row):
    items = tuple(sorted((str(item.get("uuid", "")), tuple(sorted(item.get("pos", {}).items())))
                         for item in row.get("items", [])))
    return row.get("group"), row.get("type"), row.get("severity"), items


def old_added(before, after):
    remaining = (Counter(old_key(row) for row in after if row.get("severity") == "error"
                         and not row.get("excluded", False))
                 - Counter(old_key(row) for row in before if row.get("severity") == "error"
                           and not row.get("excluded", False)))
    output = []
    for row in after:
        if row.get("severity") == "error" and not row.get("excluded", False) and remaining[old_key(row)]:
            output.append(row)
            remaining[old_key(row)] -= 1
    return output


class FindingTests(unittest.TestCase):
    def test_every_finding_validates_against_schema(self):
        validator = Draft202012Validator(SCHEMA)
        for source in ("erc", "drc", "parity", "engine", "calibration", "readback"):
            with self.subTest(source=source):
                rows = normalize_findings([finding(), finding(severity="warning")], source)
                for row in rows:
                    validator.validate(row)
                    self.assertEqual(row["source"], source)
                    self.assertEqual(row["confidence"], "deterministic")
                self.assertNotEqual(rows[0]["finding_id"], rows[1]["finding_id"])
        validator.validate(normalize_findings([finding(severity="info")], "engine")[0])

    def test_native_fields_preserved_and_input_not_mutated(self):
        raw = finding(excluded=False, native_extra={"value": [1, 2]})
        raw["items"][0].update(reference="J1", pin="1", net="GND", sheet="/power/")
        original = copy.deepcopy(raw)
        normalized = normalize_findings([raw], "drc", evidence_id="ev-1")[0]
        for key in raw:
            self.assertEqual(normalized[key], raw[key])
        self.assertEqual(normalized["message"], raw["description"])
        self.assertEqual(normalized["position_mm"], [1.25, 2.5])
        self.assertEqual(normalized["evidence_id"], "ev-1")
        normalized["items"][0]["pos"]["x"] = 999
        normalized["native_extra"]["value"].append(3)
        self.assertEqual(raw, original)

    def test_moved_item_keeps_id(self):
        original, moved = finding(), finding(x=100, y=200)
        self.assertEqual(finding_key(original), finding_key(moved))
        self.assertEqual(added_errors(dict(findings=[original]), dict(findings=[moved])), [])
        self.assertNotEqual(old_key(original), old_key(moved))

    def test_duplicate_keys_get_stable_suffix(self):
        one, two = finding(), finding()
        one["description"], two["description"] = "first", "second"
        rows = normalize_findings([one, two])
        reversed_rows = normalize_findings([two, one])
        self.assertEqual({r["description"]: r["finding_id"] for r in rows},
                         {r["description"]: r["finding_id"] for r in reversed_rows})
        self.assertEqual([r["finding_id"].split("#")[-1] for r in rows], ["1", "2"])
        self.assertEqual(rows, normalize_findings(rows))

    def test_uuidless_item_uses_rounded_pos(self):
        a = finding(uuid="", x=1.23441)
        b = finding(uuid="", x=1.23449)
        c = finding(uuid="", x=1.2346)
        self.assertEqual(finding_key(a), finding_key(b))
        self.assertNotEqual(finding_key(a), finding_key(c))
        self.assertEqual(finding_key(finding(uuid="", x=-0.0)), finding_key(finding(uuid="", x=0.0)))
        mixed_a = finding()
        mixed_a["items"].append(dict(pos=dict(x=1, y=2)))
        mixed_b = copy.deepcopy(mixed_a)
        mixed_b["items"][0]["pos"]["x"] = 500
        self.assertEqual(finding_key(mixed_a), finding_key(mixed_b))
        mixed_b["items"][1]["pos"]["x"] = 500
        self.assertNotEqual(finding_key(mixed_a), finding_key(mixed_b))

    def test_item_order_and_nonidentity_metadata_do_not_change_id(self):
        row = finding()
        row["items"].append(dict(uuid="pad-2", pos=dict(x=3, y=4)))
        other = copy.deepcopy(row)
        other["items"].reverse()
        other.update(description="Translated text", evidence_id="other-evidence", file="/other/temp/board.kicad_pcb")
        self.assertEqual(finding_key(row), finding_key(other))
        for changed in (dict(row, type="shorting_items"), dict(row, group="unconnected_items"),
                        dict(row, source="erc")):
            self.assertNotEqual(finding_key(row), finding_key(changed))

    def test_parity_and_erc_source_are_derived_from_check(self):
        parity = dict(finding(), group="schematic_parity")
        self.assertEqual(normalize_findings([parity], "drc")[0]["source"], "parity")
        self.assertEqual(normalize_findings([dict(finding(), sheet="/")])[0]["source"], "erc")
        # Native source metadata cannot relabel an explicit KiCad check.
        self.assertEqual(normalize_findings([dict(finding(), source="engine")], "erc")[0]["source"], "erc")

    def test_engine_confidence_and_evidence_source_preserved(self):
        raw = finding(severity="info", confidence="heuristic", evidence_source="calculation")
        row = normalize_findings([raw], "engine")[0]
        self.assertEqual(row["confidence"], "heuristic")
        self.assertEqual(row["evidence_source"], "calculation")
        self.assertEqual(normalize_findings([row])[0], row)

    def test_excluded_severity_preserves_native_value(self):
        for severity in ("exclusion", "ignore"):
            row = normalize_findings([finding(severity=severity)])[0]
            self.assertEqual(row["severity"], "warning")
            self.assertTrue(row["excluded"])
            self.assertEqual(row["raw_severity"], severity)
            self.assertEqual(normalize_findings([row])[0], row)
        row = normalize_findings([finding(severity="ignore", original_severity="error")])[0]
        self.assertEqual(row["severity"], "error")
        self.assertEqual(added_errors(dict(findings=[]), dict(findings=[row])), [])
        for original in (None, "unknown"):
            row = normalize_findings([finding(severity="exclusion", original_severity=original)])[0]
            self.assertEqual(row["severity"], "warning")
            self.assertTrue(row["excluded"])

    def test_invalid_report_fails_closed(self):
        malformed = [finding(severity="fatal"), finding(severity=["error"]), finding(excluded="false"),
                     dict(finding(), items="code"), finding(x=float("nan")), finding(y=float("inf")),
                     finding(x="1.5"), dict(finding(), items=[dict(uuid=5)]), finding(rule=""),
                     finding(confidence="unsupported"), dict(finding(), source="unsupported")]
        for raw in malformed:
            with self.subTest(raw=raw), self.assertRaises(PcbAiError) as caught:
                normalize_findings([raw], "engine" if raw.get("confidence") else None)
            self.assertEqual(caught.exception.code, "invalid_report")

    def test_added_errors_equivalence(self):
        a, b = finding(), finding(rule="shorting_items")
        warning, excluded = finding(severity="warning"), finding(excluded=True)
        cases = [([], []), ([], [a]), ([a], [a]), ([a], [b]), ([a], [a, b]),
                 ([a], [a, a]), ([a, a], [a]), ([warning], [a]), ([a], [warning]),
                 ([excluded], [a]), ([a], [excluded]), ([a, warning], [a]),
                 ([a], [a, warning]), ([a], [dict(a, group="schematic_parity")])]
        for before, after in cases:
            with self.subTest(before=before, after=after):
                expected = old_added(before, after)
                self.assertEqual(added_errors(dict(findings=before), dict(findings=after)), expected)
                normalized_before, normalized_after = normalize_findings(before), normalize_findings(after)
                added = added_errors(dict(findings=normalized_before), dict(findings=normalized_after))
                self.assertEqual([old_key(row) for row in added], [old_key(row) for row in expected])

    def test_engine_preview_findings_validate(self):
        flow = test_route_engines.EngineFlowTests("test_same_count_new_drc_blocks_apply")
        flow.setUp()
        self.addCleanup(flow.tearDown)
        flow.rule.stop()
        before, after = finding(), finding(rule="shorting_items")
        with patch("pcbai.tools.engine.rule_check", side_effect=[test_route_engines.check([before]),
                                                               test_route_engines.check([after])]):
            preview = flow.preview()
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(preview["blockers"], ["new_violations"])
        for row in preview["new_findings"] + preview["drc_before_findings"]:
            Draft202012Validator(SCHEMA).validate(row)

    def test_check_output_preserves_raw_evidence(self):
        with tempfile.TemporaryDirectory(prefix="pcbai-finding-output-") as tmp:
            root = Path(tmp)
            project = make_project(root / "project")
            state = root / "state"
            state.mkdir()
            engine = Engine([project], state)
            try:
                session = next(iter(engine.sessions.entries.values()))
                raw = finding()
                report = dict(violations=[copy.deepcopy(raw)], unconnected_items=[], schematic_parity=[])
                check = dict(errors=1, warning_count=0, findings=[raw], report=report, clean=False)
                with patch("pcbai.tools.engine.rule_check", return_value=check):
                    response = engine.call("drc", session.target("Test.kicad_pcb"))
                self.assertTrue(response["ok"], response)
                row = response["findings"][0]
                self.assertEqual(row["evidence_id"], response["evidence_id"])
                self.assertEqual(row["description"], raw["description"])
                evidence = json.loads((engine.evidence.root / (response["evidence_id"] + ".json"))
                                      .read_text(encoding="utf-8"))
                self.assertEqual(evidence["report"], report)
                self.assertNotIn("finding_id", evidence["report"]["violations"][0])
            finally:
                engine.jobs.close()

    def test_kicad_plugin_check_lines_still_render(self):
        module_path = Path(__file__).resolve().parents[1] / "kicad_plugin/assistant_core.py"
        spec = importlib.util.spec_from_file_location("pcbai_test_plugin_core", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        response = dict(ok=True, verified="checks_findings", summary="DRC: 1 error", warnings=[], findings=[finding()])
        original = module.check_lines(response)
        normalized = module.check_lines(dict(response, findings=normalize_findings(response["findings"])))
        self.assertEqual(original, normalized)
        self.assertIn("Native description", normalized[-1])
        self.assertIn("(1.25, 2.5)", normalized[-1])


class RealFindingTests(unittest.TestCase):
    def test_same_input_same_ids_real_kicad(self):
        demos = demo_root()
        if demos is None:
            self.skipTest("Installed KiCad CLI and ecc83-pp demo required")
        source = demos / "ecc83"
        before = source_hashes(source)
        results = []
        with tempfile.TemporaryDirectory(prefix="pcbai-finding-repeat-") as tmp:
            for name in ("first", "second"):
                root = Path(tmp) / name
                project = root / "project"
                shutil.copytree(source, project)
                state = root / "state"
                state.mkdir()
                engine = Engine([project / "ecc83-pp.kicad_pro"], state)
                try:
                    session = next(iter(engine.sessions.entries.values()))
                    response = engine.call("drc", session.target("ecc83-pp.kicad_pcb"))
                    self.assertTrue(response["ok"], response)
                    self.assertEqual(response["verified"], "drc_findings")
                    self.assertTrue(response["findings"])
                    for row in response["findings"]:
                        Draft202012Validator(SCHEMA).validate(row)
                    results.append(sorted(row["finding_id"] for row in response["findings"]))
                finally:
                    engine.jobs.close()
        self.assertEqual(results[0], results[1])
        self.assertEqual(source_hashes(source), before)
