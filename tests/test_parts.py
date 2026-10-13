import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pcbai.core.contract import PcbAiError
from pcbai.parts.index import PartIndex
from pcbai.parts.library import read_library, read_metadata, symbol, verify_part
from pcbai.sch.model import properties

LIBRARY = b'''(kicad_symbol_lib (version 20231120) (generator "test")
  (symbol "Base" (property "Reference" "U") (property "Value" "Base")
    (symbol "Base_1_1" (pin power_in line (at 0 0 0) (length 2.54) (name "IN") (number "01"))
                       (pin power_out line (at 5 0 180) (length 2.54) (name "OUT") (number "A1"))))
  (symbol "AMS1117-3.3" (extends "Base") (property "Value" "AMS1117-3.3")
    (property "Description" "LDO 3.3 V regulator") (property "Footprint" "Test:Multi"))
  (symbol "Cycle" (extends "Cycle")))'''
FOOTPRINT = b'''(footprint "Multi" (pad "01" smd rect (at 0 0) (size 1 1))
  (pad "A1" smd rect (at 5 0) (size 1 1)) (pad "A1" smd rect (at 5 1) (size 1 1))
  (pad "" np_thru_hole circle (at 10 10) (size 2 2) (drill 2)))'''


class PartTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        symbols = self.root / "symbols"
        symbols.mkdir()
        (symbols / "Test.kicad_sym").write_bytes(LIBRARY)
        footprints = self.root / "footprints/Test.pretty"
        footprints.mkdir(parents=True)
        (footprints / "Multi.kicad_mod").write_bytes(FOOTPRINT)
        self.env = patch.dict(os.environ, PCBAI_SYMBOLS=str(symbols), PCBAI_FOOTPRINTS=str(footprints.parent))
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_inheritance_unique_pins_multi_pad_and_mechanical_pad(self):
        info = symbol("Test:AMS1117-3.3")
        self.assertEqual(info["properties"]["Value"], "AMS1117-3.3")
        self.assertEqual({p["number"] for p in info["pins"]}, {"01", "A1"})
        self.assertNotIn(b'(extends', info["data"])
        self.assertIn(b'AMS1117-3.3_1_1', info["data"])
        verified = verify_part("Test:AMS1117-3.3", "Test:Multi")
        self.assertTrue(verified["pin_pad_match"])
        self.assertFalse(verified["stock_verified"])
        self.assertIsNone(verified["datasheet_match"])
        self.assertEqual(verified["pin_numbers"], ["01", "A1"])
        self.assertTrue(verify_part("Test:Base", "Test:Multi", {"01": "IN", "A1": "OUT"})["datasheet_match"])
        self.assertFalse(verify_part("Test:Base", "Test:Multi", {"1": "IN", "A1": "OUT"})["datasheet_match"])

    def test_index_search_terms_are_data_and_cache_refreshes(self):
        index = PartIndex(self.root)
        self.assertEqual(index.search("AMS1117 3.3")[0]["lib_id"], "Test:AMS1117-3.3")
        self.assertEqual(index.search("AMS1117 OR DROP TABLE"), [])
        file = self.root / "symbols/Test.kicad_sym"
        file.write_bytes(LIBRARY.replace(b'3.3', b'5.0'))
        self.assertEqual(index.search("AMS1117 3.3"), [])
        self.assertEqual(index.search("AMS1117 5.0")[0]["lib_id"], "Test:AMS1117-5.0")

    def test_escape_missing_inheritance_cycle_and_hardlink_database_refused(self):
        for name in ("../Test:Base", "Test:../x", "Test:Cycle", "Test:Missing"):
            with self.assertRaises(PcbAiError):
                symbol(name)
        index = PartIndex(self.root)
        sentinel = self.root / "sentinel"
        sentinel.write_text("KEEP", encoding="utf-8")
        os.link(sentinel, index.path)
        with self.assertRaises(ValueError):
            index.search("AMS1117")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "KEEP")

    def test_inherited_index_metadata_and_content_hash_refresh(self):
        index = PartIndex(self.root)
        file = self.root / "symbols/Test.kicad_sym"
        library = LIBRARY.replace(b'(property "Value" "Base")', b'(property "Value" "Base") (property "Description" "common amplifier")')
        file.write_bytes(library)
        results = index.search("common amplifier")
        self.assertEqual({r["lib_id"] for r in results}, {"Test:Base"})
        self.assertTrue(any(w["lib_id"] == "Test:Cycle" for w in index.warnings))
        # Child overrides Description, but inherits parent's Datasheet/keywords.
        library = library.replace(b'(property "Value" "Base")', b'(property "Value" "Base") (property "ki_keywords" "inheritedkeyword")')
        file.write_bytes(library)
        self.assertEqual({r["lib_id"] for r in index.search("inheritedkeyword")}, {"Test:Base", "Test:AMS1117-3.3"})
        old_time = file.stat().st_mtime_ns
        file.write_bytes(library.replace(b'inheritedkeyword', b'differentkeyword'))
        os.utime(file, ns=(old_time, old_time))
        self.assertEqual(index.search("inheritedkeyword"), [])

    def test_database_auxiliary_hardlink_is_refused(self):
        index = PartIndex(self.root)
        sentinel = self.root / "KEEP"
        sentinel.write_bytes(b"KEEP")
        os.link(sentinel, index.path.with_name(index.path.name + "-journal"))
        with self.assertRaises(ValueError):
            index.search("AMS1117")
        self.assertEqual(sentinel.read_bytes(), b"KEEP")

    def test_numbered_npth_is_not_an_electrical_pin_counterpart(self):
        file = self.root / "footprints/Test.pretty/Multi.kicad_mod"
        file.write_bytes(FOOTPRINT.replace(b'"01" smd', b'"01" np_thru_hole'))
        result = verify_part("Test:Base", "Test:Multi")
        self.assertFalse(result["pin_pad_match"])
        self.assertEqual(result["missing_pads"], ["01"])
        self.assertTrue(any(p["number"] == "01" for p in result["mechanical_pads"]))

    def test_metadata_scan_matches_full_parser_and_refuses_broken_roots(self):
        file = self.root / "symbols/Test.kicad_sym"
        full, full_nodes = read_library(file)
        scanned, scanned_nodes = read_metadata(file)
        self.assertEqual(full, scanned)
        self.assertEqual(set(full_nodes), set(scanned_nodes))
        for name in full_nodes:
            self.assertEqual(properties(full_nodes[name]), properties(scanned_nodes[name]))
        for data in (LIBRARY[:-1], LIBRARY + b')', LIBRARY + LIBRARY, b'(kicad_symbol_lib (symbol "oops))'):
            file.write_bytes(data)
            with self.assertRaises(PcbAiError):
                read_metadata(file)
