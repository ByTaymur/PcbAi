import shutil
import tempfile
import unittest
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.fab.connections import check, reconcile, schematic_authority
from pcbai.fab.gerber import parse, islands
from pcbai.fab.ipc356 import parse as parse_ipc
from pcbai.kicad.files import revision
from pcbai.verify.manifest import verification

HEADER = '%TF.FileFunction,Copper,L1,Top*%\n%TF.FilePolarity,Positive*%\n%FSLAX46Y46*%\n%MOMM*%\n%LPD*%\nG01*\n'
BODY = '%ADD10R,1X1*%\n%ADD11C,0.25*%\nD10*\n%TO.P,J1,1*%\nX5000000Y-5000000D03*\n%TD*%\n%TO.P,J2,1*%\nX10000000Y-5000000D03*\n%TD*%\nD11*\nX5000000Y-5000000D02*\nX10000000Y-5000000D01*\n'
IPC = b'P  CODE 00\nP  UNITS CUST 0\nP  arrayDim   N\n327/LEFT            J1    -1          A01X+001969Y-001969X0394Y0394R000S2\n327/LEFT            J2    -1          A01X+003937Y-001969X0394Y0394R000S2\n999\n'


class FabricationConnectionsTests(unittest.TestCase):
    def layer(self, body=BODY):
        layer = parse((HEADER+body+'M02*\n').encode())
        layer["islands"] = islands(layer["shapes"])
        return layer

    def test_physical_short_is_independent_of_artwork_net_labels(self):
        layer = self.layer()
        self.assertEqual(len(set(layer["islands"])), 1)
        native = dict(pins={("J1", "1"): "/LEFT", ("J2", "1"): "/RIGHT"})
        rows, checks, registered = reconcile({"F.Cu": layer}, parse_ipc(IPC), native)
        self.assertEqual({row["rule_id"] for row in rows}, {"gerber_schematic_short", "ipc_schematic_partition_conflict"})
        self.assertEqual(verification(checks, rows), "checks_findings")
        self.assertEqual(len(registered), 2)
        self.assertTrue(all(row["source"] == "fab" for row in rows))

    def test_consistent_artwork_ipc_schematic_is_clean_in_explicit_scope(self):
        layer = self.layer()
        native = dict(pins={("J1", "1"): "/LEFT", ("J2", "1"): "/LEFT"})
        rows, checks, _ = reconcile({"F.Cu": layer}, parse_ipc(IPC), native)
        self.assertEqual(verification(checks, rows), "checks_ok")
        self.assertEqual(rows, [])

    def test_artwork_short_between_distinct_ipc_labels_is_reported(self):
        ipc = parse_ipc(IPC)
        ipc["points"][1]["net"] = "/RIGHT"
        native = dict(pins={("J1", "1"): "/LEFT", ("J2", "1"): "/RIGHT"})
        rows, _, _ = reconcile({"F.Cu": self.layer()}, ipc, native)
        self.assertIn("gerber_ipc_short", {row["rule_id"] for row in rows})

    def test_native_schematic_identity_cannot_silently_collapse(self):
        xml = b'<export><sheet number="1"/><components><comp ref="J1"/></components><nets><net code="1" name="LEFT"><node ref="J1" pin="1"/></net></nets></export>'
        self.assertEqual(schematic_authority(xml)["pins"], {("J1", "1"): "LEFT"})
        for raw in (xml.replace(b'<comp ref="J1"/>', b'<comp ref="J1"/><comp ref="j1"/>'),
                    xml.replace(b'<node ref="J1" pin="1"/>', b'<node ref="J1" pin="1"/><node ref="J1" pin="1"/>'),
                    xml.replace(b'name="LEFT"', b'name=""'), xml.replace(b'ref="J1" pin="1"', b'ref="J2" pin="1"')):
            with self.assertRaises(PcbAiError):
                schematic_authority(raw)
        for suffix in (b'<net code="2" name="LEFT"/>', b'<net code="1" name="RIGHT"/>'):
            with self.assertRaises(PcbAiError):
                schematic_authority(xml.replace(b'</nets>', suffix+b'</nets>'))

    def test_disconnected_geometry_detects_open_without_renaming_ipc_nets(self):
        body = BODY.replace('X10000000Y-5000000D01*', 'X7000000Y-5000000D01*')
        native = dict(pins={("J1", "1"): "/LEFT", ("J2", "1"): "/LEFT"})
        rows, checks, _ = reconcile({"F.Cu": self.layer(body)}, parse_ipc(IPC), native)
        self.assertIn("gerber_schematic_open", {row["rule_id"] for row in rows})
        self.assertEqual(verification(checks, rows), "checks_findings")

    def test_shifted_or_unregistered_pad_prevents_complete_coverage(self):
        native = dict(pins={("J1", "1"): "/LEFT", ("J2", "1"): "/LEFT"})
        ipc = parse_ipc(IPC)
        ipc["points"][0]["x_mm"] += .1
        rows, checks, registered = reconcile({"F.Cu": self.layer()}, ipc, native)
        self.assertEqual(verification(checks, rows), "checks_incomplete")
        self.assertEqual(len(registered), 1)

    def test_duplicate_pin_flash_cannot_hide_physical_contact(self):
        body = BODY.split('D11*')[0] + '%TO.P,J1,1*%\nX10000000Y-5000000D03*\n%TD*%\n'
        native = dict(pins={("J1", "1"): "/LEFT", ("J2", "1"): "/RIGHT"})
        ipc = parse_ipc(IPC)
        ipc["points"][1]["net"] = "/RIGHT"
        rows, checks, registered = reconcile({"F.Cu": self.layer(body)}, ipc, native)
        self.assertEqual(verification(checks, rows), "checks_incomplete")
        self.assertEqual(len(registered), 1)

    def test_unknown_geometry_is_rejected_instead_of_silently_skipped(self):
        for command in ('%LPC*%', '%LR90*%', '%AMfoo*1,1,1,0,0*%', 'G02*', 'G36*', '%SRX2Y2I1J1*%', 'G99*'):
            with self.subTest(command=command), self.assertRaises(PcbAiError):
                parse((HEADER+command+'\n'+BODY+'M02*').encode())
        for suffix in ('', 'M02*X0Y0D01*'):
            with self.assertRaises(PcbAiError):
                parse((HEADER+BODY+suffix).encode())

    def test_ipc_units_termination_duplicate_and_plated_records_fail_closed(self):
        for raw in (IPC.replace(b'CUST 0', b'CUST 2'), IPC.replace(b'999\n', b''), IPC+b'327bad\n',
                    IPC.replace(b'327/LEFT', b'317/LEFT', 1), IPC.replace(b'J2    -1', b'J1    -1')):
            with self.subTest(raw=raw[:40]), self.assertRaises(PcbAiError):
                parse_ipc(raw)

    def test_ipc_literal_negative_pin_keeps_its_identity(self):
        parsed = parse_ipc(IPC.replace(b'J1    -1 ', b'J1    --1'))
        self.assertEqual(parsed["points"][0]["pin"], "-1")
        for raw in (IPC.replace(b'J1    -1', b'ABCDEF-1'), IPC.replace(b'-1   ', b'-1234')):
            with self.assertRaises(PcbAiError):
                parse_ipc(raw)

    def test_rect_capsule_and_obround_contacts_are_geometric(self):
        layer = self.layer('%ADD10O,2X1*%\nD10*\nX0Y0D03*\nX2000000Y0D03*\n')
        self.assertEqual(len(set(layer["islands"])), 1)
        separate = self.layer('%ADD10O,2X1*%\nD10*\nX0Y0D03*\nX2100000Y0D03*\n')
        self.assertEqual(len(set(separate["islands"])), 2)

    def test_tangent_contact_uses_exact_decimal_geometry_without_gap_epsilon(self):
        tangent = self.layer('%ADD10C,0.2*%\nD10*\nX1900000Y0D03*\nX2100000Y0D03*\n')
        self.assertEqual(len(set(tangent["islands"])), 1)
        gap = self.layer('%ADD10C,0.199999999*%\nD10*\nX1900000Y0D03*\nX2100000Y0D03*\n')
        self.assertEqual(len(set(gap["islands"])), 2)


class NativeFabricationConnectionsTests(unittest.TestCase):
    def test_real_drc_zero_short_is_caught_from_actual_artwork_and_ipc(self):
        from pcbai.external import find_kicad_cli
        from pcbai.kicad.cli import rule_check
        from pcbai.kicad.exports import export_fab
        try:
            find_kicad_cli()
        except PcbAiError as exc:
            self.skipTest(str(exc))
        with tempfile.TemporaryDirectory(prefix="pcbai-three-authorities-") as temporary:
            root = Path(temporary) / "project"
            shutil.copytree(Path(__file__).parent / "fixtures/faults/01-drc-zero-short", root)
            before = revision(root)
            self.assertTrue(rule_check(root, "fault.kicad_pcb", "drc", expected_revision=before)["clean"])
            output = check(root, "fault.kicad_pcb", before)
            self.assertEqual(output["verified"], "checks_findings", output)
            self.assertIn("gerber_schematic_short", {r["rule_id"] for r in output["findings"]})
            self.assertIn("ipc_schematic_partition_conflict", {r["rule_id"] for r in output["findings"]})
            self.assertEqual(len(output["registered_pads"]), 2)
            self.assertFalse(output["production_verified"])
            self.assertEqual(revision(root), before)
            package = export_fab(root, "fault.kicad_pcb", Path(temporary)/"fixture.zip", before)
            self.assertIn("B.Silkscreen", package["omitted_disabled_layers"])
            self.assertEqual(revision(root), before)
