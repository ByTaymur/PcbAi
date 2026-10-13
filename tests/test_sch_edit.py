import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from pcbai.core.contract import PcbAiError
from pcbai.parts.library import inspect_symbol
from pcbai.sch.edit import (cached_info, endpoint, hierarchy, plan_add_symbol,
                            plan_labels, plan_replace)
from pcbai.sch.model import symbols
from pcbai.service.sessions import Sessions
from pcbai.sexpr import Document

ROOT_ID = "1c9d0eb0-e4b7-400a-a62e-9c0f7a2b39a2"
DEFINITION = b'''(symbol "Test:R" (property "Reference" "R") (property "Value" "R")
  (property "Footprint" "Test:R") (property "Datasheet" "")
  (symbol "R_1_1" (pin passive line (at 0 2.54 270) (name "~") (number "01"))
                  (pin passive line (at 0 -2.54 90) (name "~") (number "A1"))))'''
ROOT = ('(kicad_sch (version 20250114) (uuid "' + ROOT_ID + '") (paper "A4") (lib_symbols ' +
        DEFINITION.decode() + '))').encode()


def context():
    return dict(project="demo", root_uuid=ROOT_ID, sheet_path="/" + ROOT_ID, references=[])


class SchEditTests(unittest.TestCase):
    def added(self, data=ROOT, **extra):
        args = dict(lib_id="Test:R", reference="R1", x_mm=25.4, y_mm=50.8, **extra)
        return plan_add_symbol(data, args, context())["data"]

    def test_project_cache_wins_and_only_inserted_bytes_change(self):
        with patch("pcbai.sch.edit.installed_symbol", side_effect=AssertionError("cache replaced")):
            edited = self.added(value='4k7 " ; (shell)')
        self.assertEqual(edited[:ROOT.rfind(b')')], ROOT[:-1])
        result = symbols(edited, "demo", ROOT_ID)[0]
        self.assertEqual(result["Value"], '4k7 " ; (shell)')
        self.assertEqual(result["reference"], "R1")
        self.assertEqual(cached_info(edited, "Test:R")["source"], "project_cache")
        self.assertEqual(len(Document(edited).root.all("symbol")), 1)

    def test_pin_anchors_at_cardinal_rotations_and_mirrors(self):
        expected = {0: [25.4, 48.26], 90: [22.86, 50.8], 180: [25.4, 53.34], 270: [27.94, 50.8]}
        for rotation in expected:
            for mirror in (None, "x", "y"):
                with self.subTest(rotation=rotation, mirror=mirror):
                    added = self.added(rotation_deg=rotation, **({"mirror": mirror} if mirror else {}))
                    p = endpoint(added, dict(reference="R1", pin="01"), context())
                    at = expected[rotation].copy()
                    if mirror == "x":
                        at[1] = round(101.6 - at[1], 6)
                    elif mirror == "y":
                        at[0] = round(50.8 - at[0], 6)
                    self.assertEqual(p["at"], at)
        with self.assertRaises(PcbAiError):
            endpoint(added, dict(reference="R1", pin="1"), context())

    def test_reference_unit_grid_uuid_and_inheritance_guards(self):
        refs = context()
        refs["references"] = [dict(reference="R1", unit=1, lib_id="Test:R", sheet_path="/" + ROOT_ID)]
        with self.assertRaises(PcbAiError):
            plan_add_symbol(ROOT, dict(lib_id="Test:R", reference="R1", x_mm=25.4, y_mm=50.8), refs)
        for kwargs in ({"x_mm": 25.41}, {"reference": "R?"}, {"value": "x\n.exe"}, {"unit": 2}):
            args = dict(lib_id="Test:R", reference="R1", x_mm=25.4, y_mm=50.8)
            args.update(kwargs)
            with self.assertRaises(PcbAiError):
                plan_add_symbol(ROOT, args, context())
        broken = ROOT.replace(b'(lib_symbols ', b'(lib_symbols (symbol "Test:Bad" (extends "Missing")) ')
        with self.assertRaises(PcbAiError):
            cached_info(broken, "Test:Bad")
        duplicate = ROOT[:-1] + ('(junction (uuid "' + ROOT_ID.upper() + '")))').encode()
        with self.assertRaises(PcbAiError):
            self.added(duplicate)

    def test_connect_literals_duplicate_endpoint_and_foreign_instances(self):
        data = self.added()
        data = plan_add_symbol(data, dict(lib_id="Test:R", reference="R2", x_mm=50.8, y_mm=50.8), context())["data"]
        args = dict(name="NODE", endpoints=[dict(reference="R1", pin="01"), dict(reference="R2", pin="A1")])
        labels = plan_labels(data, args, context(), connect=True)
        self.assertEqual(len(Document(labels["data"]).root.all("label")), 2)
        self.assertEqual(len(labels["endpoints"]), 2)
        with self.assertRaises(PcbAiError):
            plan_labels(data, dict(args, endpoints=[args["endpoints"][0]] * 2), context(), connect=True)
        foreign = data.replace(b'(project "demo"', b'(project "foreign"')
        with self.assertRaises(PcbAiError):
            endpoint(foreign, dict(reference="R1", pin="01"), context())

    def test_replacement_preserves_pin_uuids_and_refuses_displaced_pin(self):
        data = self.added()
        good = DEFINITION.replace(b'Test:R', b'Test:New').replace(b'"R_1_1"', b'"New_1_1"')
        info = dict(inspect_symbol(good, "Test:New"), source="kicad", definition_sha256="test")
        with patch("pcbai.sch.edit.installed_symbol", return_value=info):
            changed = plan_replace(data, dict(reference="R1", lib_id="Test:New"), context())["data"]
        old_node, new_node = Document(data).root.all("symbol")[0], Document(changed).root.all("symbol")[0]
        self.assertEqual(old_node.child("uuid").value(), new_node.child("uuid").value())
        self.assertEqual([p.child("uuid").value() for p in old_node.all("pin")], [p.child("uuid").value() for p in new_node.all("pin")])
        displaced = dict(info, data=good.replace(b'0 2.54', b'0 5.08'))
        with patch("pcbai.sch.edit.installed_symbol", return_value=displaced), self.assertRaises(PcbAiError):
            plan_replace(data, dict(reference="R1", lib_id="Test:New"), context())

    def test_hierarchy_single_child_root_context_and_shared_child_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "demo.kicad_pro").write_text(json.dumps({}), encoding="utf-8")
            (root / "child.kicad_sch").write_bytes(ROOT.replace(ROOT_ID.encode(), str(uuid.uuid4()).encode()))
            sheet = f'(sheet (uuid "{uuid.uuid4()}") (property "Sheetfile" "child.kicad_sch"))'
            (root / "demo.kicad_sch").write_bytes(ROOT[:-1] + sheet.encode() + b')')
            session = next(iter(Sessions([root / "demo.kicad_pro"]).entries.values()))
            result = hierarchy(session, "child.kicad_sch")
            self.assertEqual(result["check_document"], "demo.kicad_sch")
            self.assertTrue(result["sheet_path"].startswith("/" + ROOT_ID + "/"))
            (root / "demo.kicad_sch").write_bytes(ROOT[:-1] + sheet.encode() +
                sheet.replace(sheet.split('"')[1], str(uuid.uuid4())).encode() + b')')
            with self.assertRaises(PcbAiError) as caught:
                hierarchy(session, "child.kicad_sch")
            self.assertEqual(caught.exception.code, "shared_sheet")

    def test_foreign_project_refuses_the_entire_authoring_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "demo.kicad_pro").write_text("{}", encoding="utf-8")
            (root / "demo.kicad_sch").write_bytes(self.added().replace(b'(project "demo"', b'(project "foreign"'))
            session = next(iter(Sessions([root / "demo.kicad_pro"]).entries.values()))
            with self.assertRaises(PcbAiError) as caught:
                hierarchy(session, "demo.kicad_sch")
            self.assertEqual(caught.exception.code, "shared_sheet")

    def test_common_unit_only_power_flag_supports_one_logical_unit(self):
        common = ROOT.replace(b'"R_1_1"', b'"R_0_1"')
        added = self.added(common)
        self.assertEqual(endpoint(added, dict(reference="R1", pin="01"), context())["at"], [25.4, 48.26])
        with self.assertRaises(PcbAiError):
            self.added(common, unit=2)
        self.assertEqual(symbols(plan_add_symbol(common, dict(lib_id="Test:R", reference="#PWR01",
            x_mm=25.4, y_mm=50.8), context())["data"])[0]["reference"], "#PWR01")

    def test_sibling_project_blank_child_cannot_be_authored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "child.kicad_sch").write_bytes(ROOT)
            for name in ("first", "second"):
                (root / (name + ".kicad_pro")).write_text("{}", encoding="utf-8")
                sheet = f'(sheet (uuid "{uuid.uuid4()}") (property "Sheetfile" "child.kicad_sch"))'
                (root / (name + ".kicad_sch")).write_bytes(ROOT[:-1] + sheet.encode() + b')')
            session = next(iter(Sessions([root / "first.kicad_pro"]).entries.values()))
            with self.assertRaises(PcbAiError) as caught:
                hierarchy(session, "child.kicad_sch")
            self.assertEqual(caught.exception.code, "shared_sheet")

    def test_foreign_sheet_records_block_root_and_its_blank_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "demo.kicad_pro").write_text("{}", encoding="utf-8")
            (root / "child.kicad_sch").write_bytes(ROOT)
            sheet = (f'(sheet (uuid "{uuid.uuid4()}") (property "Sheetfile" "child.kicad_sch") '
                     f'(instances (project "demo" (path "/{ROOT_ID}" (page "2"))) '
                     f'(project "foreign" (path "/{uuid.uuid4()}" (page "3")))))')
            (root / "demo.kicad_sch").write_bytes(ROOT[:-1] + sheet.encode() + b')')
            session = next(iter(Sessions([root / "demo.kicad_pro"]).entries.values()))
            for document in ("demo.kicad_sch", "child.kicad_sch"):
                with self.subTest(document=document), self.assertRaises(PcbAiError) as caught:
                    hierarchy(session, document)
                self.assertEqual(caught.exception.code, "shared_sheet")

    def test_uuid_case_and_dash_variants_do_not_hide_global_references(self):
        from pcbai.sch.scene import scene_sch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "demo.kicad_pro").write_text("{}", encoding="utf-8")
            (root / "child.kicad_sch").write_bytes(ROOT)
            data = self.added().replace(('(uuid "' + ROOT_ID + '")').encode(),
                                       ('(uuid "' + ROOT_ID.upper().replace('-', '') + '")').encode())
            sheet = f'(sheet (uuid "{uuid.uuid4()}") (property "Sheetfile" "child.kicad_sch"))'
            (root / "demo.kicad_sch").write_bytes(data[:-1] + sheet.encode() + b')')
            session = next(iter(Sessions([root / "demo.kicad_pro"]).entries.values()))
            ctx = hierarchy(session, "child.kicad_sch")
            self.assertEqual([r["reference"] for r in ctx["references"]], ["R1"])
            with self.assertRaises(PcbAiError) as caught:
                plan_add_symbol(ROOT, dict(lib_id="Test:R", reference="R1", x_mm=25.4, y_mm=50.8), ctx)
            self.assertEqual(caught.exception.code, "duplicate_reference")
            rendered = scene_sch(data, "/" + ROOT_ID.upper().replace('-', ''))
            self.assertEqual([i["reference"] for i in rendered["items"] if i["type"] == "symbol"], ["R1"])
