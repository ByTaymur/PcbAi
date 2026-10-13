import unittest

from pcbai.core.contract import PcbAiError
from pcbai.sch.model import edit_value, footprints, plan_value_edit, symbols
from pcbai.sexpr import Document
from tests.helpers import PCB, SCHEMATIC, shared_schematic


class SExprTests(unittest.TestCase):
    def test_roundtrip_with_unicode_crlf_comments_and_escapes(self):
        data = '; preserved\r\n(root\r\n (text "Türkçe \\"alıntı\\" \\\\ yol\\n"))\r\n'.encode()
        self.assertEqual(Document(data).serialize(), data)

    def test_deep_expression_does_not_recurse(self):
        data = b"(r " * 2000 + b"a" + b")" * 2000
        self.assertEqual(Document(data).serialize(), data)

    def test_literal_controls_in_real_kicad_strings(self):
        data = b'(root (description "\tconnector\nsecond line"))'
        document = Document(data)
        self.assertEqual(document.root.child("description").value(), "\tconnector\nsecond line")
        self.assertEqual(document.serialize(), data)

    def test_invalid_document_rejected(self):
        for data in [b"", b")", b"(x", b'(x "bad)', b"(a)(b)", b'("\\q")', b"(\xff)"]:
            with self.subTest(data=data), self.assertRaises(PcbAiError):
                Document(data)

    def test_value_edit_only_replaces_the_selected_bytes(self):
        changed, old = edit_value(SCHEMATIC, "R1", "4k7")
        self.assertEqual(old, "10k")
        self.assertEqual(changed, SCHEMATIC.replace(b'"Value" "10k"', b'"Value" "4k7"'))
        self.assertEqual(symbols(changed)[0]["Value"], "4k7")

    def test_unicode_value_and_quotes_roundtrip(self):
        changed, _ = edit_value(SCHEMATIC, "R1", 'ölçü "A"')
        self.assertEqual(symbols(changed)[0]["Value"], 'ölçü "A"')

    def test_multiple_units_all_updated(self):
        doc = Document(SCHEMATIC)
        symbol = doc.root.child("symbol")
        duplicate = SCHEMATIC[symbol.start:symbol.end].replace(b"(unit 1)", b"(unit 2)")
        multi = SCHEMATIC[:doc.root.end - 1] + duplicate + SCHEMATIC[doc.root.end - 1:]
        changed, _ = edit_value(multi, "R1", "22k")
        self.assertEqual([s["Value"] for s in symbols(changed)], ["22k", "22k"])

    def test_inconsistent_units_and_missing_ref_rejected(self):
        with self.assertRaises(PcbAiError):
            edit_value(SCHEMATIC, "R9", "1k")
        doc = Document(SCHEMATIC)
        symbol = doc.root.child("symbol")
        other = SCHEMATIC[symbol.start:symbol.end].replace(b'"10k"', b'"20k"')
        multi = SCHEMATIC[:doc.root.end - 1] + other + SCHEMATIC[doc.root.end - 1:]
        with self.assertRaises(PcbAiError):
            edit_value(multi, "R1", "1k")

    def test_reader_matches_existing_properties(self):
        self.assertEqual(symbols(SCHEMATIC)[0]["Reference"], "R1")
        self.assertEqual(footprints(PCB)[0]["at"], [10, 20, 90])
        self.assertFalse(symbols(SCHEMATIC)[0]["trusted"])

    def test_shared_sheet_lists_each_project_instance(self):
        data = shared_schematic(foreign=True)
        listed = symbols(data, "Test")
        self.assertEqual([s["Reference"] for s in listed], ["R203", "R303"])
        self.assertEqual([s["sheet_path"] for s in listed], ["/root/sheet-a", "/root/sheet-b"])
        self.assertEqual(len(symbols(data)), 3)
        self.assertEqual(symbols(data, "Renamed"), [])
        self.assertEqual(listed[0]["property_reference"], "STALE")

    def test_either_instance_edits_same_bytes_and_discloses_all_projects(self):
        data = shared_schematic(foreign=True)
        first = plan_value_edit(data, "R203", "47k", "Test")
        second = plan_value_edit(data, "R303", "47k", "Test")
        self.assertEqual(first, second)
        self.assertEqual(second["data"], data.replace(b'"Value" "10k"', b'"Value" "47k"'))
        self.assertEqual(second["affected_references"], ["R203", "R303", "R903"])
        self.assertEqual(len(second["affected_instances"]), 3)
        self.assertTrue(second["warnings"])
        for reference in ["STALE", "R903"]:
            with self.assertRaises(PcbAiError) as caught:
                edit_value(data, reference, "47k", "Test")
            self.assertEqual(caught.exception.code, "unknown_reference")

    def test_shared_multi_unit_edit_updates_every_unit_and_instance(self):
        data = shared_schematic(multi_unit=True)
        edit = plan_value_edit(data, "R303", "47k", "Test")
        self.assertEqual(len(edit["affected_instances"]), 4)
        self.assertEqual(edit["affected_references"], ["R203", "R303"])
        self.assertEqual([s["Value"] for s in symbols(edit["data"], "Test")], ["47k"] * 4)
        self.assertEqual(edit["data"], data.replace(b'"Value" "10k"', b'"Value" "47k"'))

    def test_duplicate_reference_unit_and_malformed_instances_rejected(self):
        data = shared_schematic().replace(b'"R303"', b'"R203"')
        with self.assertRaises(PcbAiError) as caught:
            edit_value(data, "R203", "47k", "Test")
        self.assertEqual(caught.exception.code, "ambiguous_reference")
        data = shared_schematic().replace(b'(reference "R303")', b'')
        for operation in [lambda: symbols(data), lambda: edit_value(data, "R203", "47k", "Test")]:
            with self.assertRaises(PcbAiError) as caught:
                operation()
            self.assertEqual(caught.exception.code, "invalid_document")

    def test_new_value_controls_and_surrogates_rejected(self):
        for number in [*range(32), *range(127, 160), 0xD800, 0xDFFF]:
            with self.subTest(number=number), self.assertRaises(PcbAiError) as caught:
                edit_value(SCHEMATIC, "R1", "A" + chr(number) + "B")
            self.assertEqual(caught.exception.code, "invalid_arguments")

    def test_custom_properties_cannot_replace_instance_metadata(self):
        data = shared_schematic().replace(b'(property "Value"',
                                          b'(property "trusted" "yes") (property "project" "Fake") (property "Value"')
        listed = symbols(data, "Test")
        self.assertEqual(listed[0]["project"], "Test")
        self.assertFalse(listed[0]["trusted"])
        self.assertEqual(listed[0]["properties"]["project"], "Fake")

    def test_unnamed_project_requires_matching_root_identity(self):
        data = shared_schematic().replace(b'(project "Test"', b'(project ""')
        self.assertEqual(len(symbols(data, "Test", "root")), 2)
        self.assertEqual(symbols(data, "Test", "other-root"), [])
        self.assertEqual(symbols(data, "Test"), [])
        changed, _ = edit_value(data, "R303", "47k", "Test", "root")
        self.assertEqual([s["Value"] for s in symbols(changed, "Test", "root")], ["47k"] * 2)
        with self.assertRaises(PcbAiError):
            edit_value(data, "R303", "47k", "Test", "other-root")

    def test_unnamed_foreign_roots_do_not_join_unrelated_components(self):
        data = shared_schematic().replace(b'(project "Test"', b'(project ""')
        doc = Document(data)
        node = doc.root.child("symbol")
        foreign = data[node.start:node.end].replace(b'/root/', b'/foreign/')
        data = data[:doc.root.end - 1] + foreign + data[doc.root.end - 1:]
        edit = plan_value_edit(data, "R303", "47k", "Test", "root")
        self.assertEqual(len(edit["affected_instances"]), 2)
        self.assertEqual([s["Value"] for s in symbols(edit["data"])], ["47k", "47k", "10k", "10k"])

    def test_root_uuid_alone_scopes_instance_selection(self):
        data = shared_schematic().replace(b'(project "Test"', b'(project ""')
        doc = Document(data)
        node = doc.root.child("symbol")
        foreign = data[node.start:node.end].replace(b'/root/', b'/foreign/').replace(b'"10k"', b'"20k"')
        data = data[:doc.root.end - 1] + foreign + data[doc.root.end - 1:]
        self.assertEqual(len(symbols(data, root_uuid="root")), 2)
        edit = plan_value_edit(data, "R303", "47k", root_uuid="root")
        self.assertEqual([s["Value"] for s in symbols(edit["data"])], ["47k", "47k", "20k", "20k"])

    def test_duplicate_value_and_reference_properties_rejected(self):
        for name in ["Value", "Reference"]:
            data = SCHEMATIC.replace(b'(property "Value"', f'(property "{name}" "OTHER") (property "Value"'.encode())
            for operation in [lambda data=data: symbols(data), lambda data=data: edit_value(data, "R1", "47k")]:
                with self.subTest(name=name), self.assertRaises(PcbAiError) as caught:
                    operation()
                self.assertEqual(caught.exception.code, "invalid_document")

    def test_shared_warning_does_not_claim_foreign_projects(self):
        edit = plan_value_edit(shared_schematic(), "R303", "47k", "Test")
        self.assertTrue(edit["warnings"])
        self.assertNotIn("other projects", edit["warnings"][0])
