"""Characterize saved-file checks; a clean DRC is not an intent check."""
import hashlib
import json
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli, run
from pcbai.sexpr import Document
from pcbai.tools.engine import Engine


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "faults"


def source_hashes(folder):
    result = {}
    for path in sorted(folder.rglob("*")):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise AssertionError("Fixture links are not allowed")
        path.resolve().relative_to(folder.resolve())
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


class FaultFixtureTests(unittest.TestCase):
    def setUp(self):
        try:
            self.cli = find_kicad_cli()
        except PcbAiError as exc:
            if exc.code == "missing_dependency":
                self.skipTest("Real KiCad CLI required: " + str(exc))
            raise

    @contextmanager
    def fixture(self, slug):
        source = FIXTURES / slug
        before = source_hashes(source)
        try:
            with tempfile.TemporaryDirectory(prefix="pcbai-fault-") as temporary:
                root = Path(temporary)
                project = root / "project"
                shutil.copytree(source, project)
                state = root / "state"
                state.mkdir()
                engine = Engine([project / "fault.kicad_pro"], state)
                session = next(iter(engine.sessions.entries.values()))
                try:
                    yield engine, session, project
                finally:
                    engine.jobs.close()
        finally:
            self.assertEqual(source_hashes(source), before, "Source fixture changed during measurement")

    def assert_clean_drc(self, result):
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["verified"], "drc_ok", result)
        self.assertEqual(result["findings"], [], result)
        counts = {m["quantity"]: m["value"] for m in result["measurements"]}
        self.assertEqual(counts, {"drc_errors": 0, "drc_warnings": 0})

    def native_members(self, project):
        output = project.parent / "native.xml"
        process = run([self.cli, "sch", "export", "netlist", "--format", "kicadxml",
                       "--output", output, project / "fault.kicad_sch"], cwd=project, timeout=60)
        self.assertEqual(process.returncode, 0, process.stderr)
        return {net.attrib["name"]: sorted([node.attrib["ref"], node.attrib["pin"]]
                                          for node in net.findall("node"))
                for net in ET.parse(output).findall("./nets/net")}

    def test_01_plain_drc_green_parity_conflict(self):
        with self.fixture("01-drc-zero-short") as (engine, session, project):
            target = session.target("fault.kicad_pcb")
            self.assert_clean_drc(engine.call("drc", target))
            parity = engine.call("drc", dict(target, parity=True))
            self.assertTrue(parity["ok"], parity)
            self.assertEqual(parity["verified"], "drc_findings", parity)
            self.assertEqual(len(parity["findings"]), 1, parity)
            finding = parity["findings"][0]
            self.assertEqual(finding["type"], "net_conflict")
            self.assertIn("J2", json.dumps(finding))
            self.assertIn("/LEFT", finding["description"])
            self.assertIn("/RIGHT", finding["description"])
            board = Document((project / "fault.kicad_pcb").read_bytes())
            j2 = next(fp for fp in board.root.all("footprint")
                      if any(p.value() == "Reference" and p.value(2) == "J2" for p in fp.all("property")))
            pad = next(p for p in j2.all("pad") if p.value() == "1")
            self.assertIn(pad.child("uuid").value(), [item["uuid"] for item in finding["items"]])

    def test_09_native_members_disagree_with_reported_json(self):
        with self.fixture("09-wrong-net-members") as (engine, session, project):
            target = session.target("fault.kicad_pcb")
            for parity in (False, True):
                self.assert_clean_drc(engine.call("drc", dict(target, parity=parity)))
            native = self.native_members(project)
            self.assertEqual(native, {"/LEFT": [["J1", "1"]], "/RIGHT": [["J2", "1"]]})
            reported = json.loads((project / "reported-net-members.json").read_text(encoding="utf-8"))["nets"]
            self.assertEqual(reported, {"/LEFT": [["J2", "1"]], "/RIGHT": [["J1", "1"]]})
            self.assertNotEqual(native, reported)
            # Dropping names hides the swap; the current DRC did not consume this JSON.
            self.assertEqual(sorted(native.values()), sorted(reported.values()))
            from pcbai.verify.calibrate import calibrate
            comparison = calibrate(dict(nets=native), dict(nets=reported))
            self.assertEqual(sum(f["rule_id"] == "net_name_member_swap" for f in comparison["findings"]), 2)

    def test_12_missing_cli_is_not_run(self):
        with self.fixture("12-missing-required-tool") as (engine, session, project):
            with patch.dict("os.environ", {"PCBAI_KICAD_CLI": str(project / "intentionally-absent-kicad-cli")}):
                result = engine.call("erc", session.target("fault.kicad_sch"))
            self.assertFalse(result["ok"], result)
            self.assertFalse(result["changed"], result)
            self.assertEqual(result["verified"], "not_run", result)
            self.assertEqual(result["error"]["code"], "missing_dependency", result)
            self.assertEqual(result["measurements"], [], result)
            with patch.dict("os.environ", {"PCBAI_KICAD_CLI": str(project / "intentionally-absent-kicad-cli")}):
                aggregate = engine.call("check", dict(session=session.id, scope="sch"))
            self.assertEqual(aggregate["verified"], "checks_incomplete", aggregate)

    def test_01b_parity_clean_but_intent_violated(self):
        with self.fixture("01b-schematic-label-merge") as (engine, session, project):
            target = session.target("fault.kicad_pcb")
            for parity in (False, True):
                self.assert_clean_drc(engine.call("drc", dict(target, parity=parity)))
            native = self.native_members(project)
            self.assertEqual(native, {"/SENSE": [["J1", "1"], ["J2", "1"]]})
            intent = json.loads((project / "intent.json").read_text(encoding="utf-8"))["nets"]
            self.assertEqual(intent, {"/SENSE_A": [["J1", "1"]], "/SENSE_B": [["J2", "1"]]})
            # The members survived, but the two intended nets were merged.
            self.assertEqual(sorted(member for members in native.values() for member in members),
                             sorted(member for members in intent.values() for member in members))
            self.assertNotEqual(sorted(native.values()), sorted(intent.values()))
            # This assertion characterizes a known escape, not a product detector.
