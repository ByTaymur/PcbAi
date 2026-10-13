import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pcbai.kicad.files import atomic_write, digest
from pcbai.sch.edit import hierarchy, plan_add_symbol
from pcbai.tools.engine import Engine
from tests.test_engine import CLEAN
from tests.test_pcb_edit import BOARD
from tests.test_sch_authoring_integration import available

TOOLS = ("set_value", "add_symbol", "connect", "add_label", "replace_part", "add_block",
         "move_footprint", "set_track_width", "add_zone", "set_netclass", "autoroute", "autoplace", "restore_checkpoint")


@unittest.skipUnless(available(), "Installed KiCad CLI/libraries required for saved netlist readback")
class ReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pcbai-readback-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        source = Path(__file__).parent / "fixtures/faults/13-written-value-differs"
        shutil.copyfile(source / "fault.kicad_sch", self.project / "demo.kicad_sch")
        (self.project / "demo.kicad_pro").write_text(json.dumps(dict(net_settings=dict(classes=[dict(name="Default",
            clearance=.2, track_width=.25, via_diameter=.6, via_drill=.3)], netclass_patterns=[])), indent=2) + "\n", encoding="utf-8")
        (self.project / "demo.kicad_pcb").write_bytes(BOARD)
        (self.root / "state").mkdir()
        self.engine = Engine([self.project / "demo.kicad_pro"], self.root / "state")
        self.addCleanup(self.engine.jobs.close)
        self.session = next(iter(self.engine.sessions.entries.values()))
        # Synthetic PCB DRC and process inventory stay independent of the user's GUI.
        from subprocess import CompletedProcess
        guards = patch("pcbai.kicad.files.run", return_value=CompletedProcess([], 0, "", ""))
        guards.start()
        self.addCleanup(guards.stop)
        checks = patch("pcbai.tools.engine.rule_check", return_value=CLEAN)
        checks.start()
        self.addCleanup(checks.stop)

    def prepare(self, tool):
        sheet = self.project / "demo.kicad_sch"
        sch = {"set_value", "add_symbol", "connect", "add_label", "replace_part", "add_block", "restore_checkpoint"}
        document = "demo.kicad_sch" if tool in sch else "demo.kicad_pcb"
        args = dict()
        if tool in {"set_value", "replace_part", "connect"}:
            for i in (1, 2):
                data = sheet.read_bytes()
                plan = plan_add_symbol(data, dict(lib_id="Device:R", reference=f"R{i}", value="10k",
                    x_mm=50.8 + (i - 1) * 50.8, y_mm=50.8), hierarchy(self.session, document))
                sheet.write_bytes(plan["data"])
        if tool == "set_value":
            args = dict(reference="R1", value="4k7")
        elif tool == "add_symbol":
            args = dict(lib_id="Device:R", reference="R1", value="4k7", x_mm=50.8, y_mm=50.8)
        elif tool == "replace_part":
            args = dict(reference="R1", lib_id="Device:R", value="4k7")
        elif tool == "connect":
            args = dict(name="LINK", endpoints=[dict(reference="R1", pin="1"), dict(reference="R2", pin="1")])
        elif tool == "add_label":
            args = dict(name="LINK", x_mm=50.8, y_mm=50.8)
        elif tool == "add_block":
            args = dict(block="voltage_divider", params=dict(vin="12V", r_top="10k", r_bottom="10k"),
                        instance="TEST", x_mm=25.4, y_mm=50.8)
        elif tool == "move_footprint":
            args = dict(reference="R1", x_mm=11, rotation_deg=180, side="back")
        elif tool == "set_track_width":
            args = dict(uuids=["t1"], width_mm=.5)
        elif tool == "add_zone":
            args = dict(net="GND", layer="B.Cu", points_mm=[[1, 1], [39, 1], [39, 29], [1, 29]])
            refill = patch("pcbai.tools.engine.refill", side_effect=lambda root, document, data, revision: data)
            refill.start()
            self.addCleanup(refill.stop)
            fill = patch("pcbai.tools.engine.splice_fill", side_effect=lambda data, filled, uuid: (data, 0))
            fill.start()
            self.addCleanup(fill.stop)
        elif tool == "set_netclass":
            document = "demo.kicad_pro"
            args = dict(netclass="Signal", track_width_mm=.5, patterns=["SIG*"])
        elif tool in {"autoroute", "autoplace"}:
            args = dict(engine="freerouting" if tool == "autoroute" else "tracemaker")
            # Engine execution is separately tested; lifecycle consumes its frozen preview.
            fake = patch.object(self.engine, "_plan_engine", return_value=(BOARD + b"\n", "engine preview",
                dict(blockers=[], drc_before_findings=[], drc_before=dict(errors=0))))
            fake.start()
            self.addCleanup(fake.stop)
        elif tool == "restore_checkpoint":
            cp = self.engine.history.checkpoint(self.session.id, document, sheet.read_bytes() + b"\n",
                                               self.session.target(document)["revision"], "owned checkpoint")
            args = dict(checkpoint_id=cp["id"])
        target = self.session.target(document)
        preview = self.engine.call(tool, dict(target, mode="preview", **args))
        self.assertTrue(preview["ok"], preview)
        return target, preview

    def lifecycle(self, tool, corrupt=False):
        target, preview = self.prepare(tool)
        candidate = self.engine.candidates[preview["candidate_id"]]
        expected = candidate["data"]
        path = self.project / target["document"]
        if corrupt:
            # A durable, parseable wrong write. No automatic rollback may hide it.
            if tool in {"set_value", "replace_part"}:
                bad = expected.replace(b'"4k7"', b'"9k9"')
            elif tool == "add_symbol":
                bad = expected.replace(b'(at 50.8 50.8 0)', b'(at 50.81 50.8 0)', 1)
            elif tool == "add_label":
                bad = expected.replace(b'(label "LINK"', b'(label "WRONG"', 1)
            elif tool in {"connect", "add_block"}:
                from pcbai.sexpr import Document
                label = Document(expected).root.all("label")[0]
                bad = expected[:label.start] + expected[label.end:]
            elif tool == "move_footprint":
                bad = expected.replace(b'(at 11 20 180)', b'(at 11.01 20 180)', 1)
            elif tool == "set_track_width":
                bad = expected.replace(b'(width 0.5)', b'(width 0.9)', 1)
            elif tool == "add_zone":
                bad = expected.replace(b'(xy 1 1)', b'(xy 1.01 1)', 1)
            elif tool == "set_netclass":
                bad = expected.replace(b'"track_width": 0.5', b'"track_width": 0.9')
            elif tool in {"autoroute", "autoplace"}:
                from pcbai.sexpr import Document
                node = Document(expected).root.all("segment")[0]
                bad = expected[:node.start] + expected[node.end:]
            else:
                bad = expected + b"\n "
            self.assertNotEqual(bad, expected)
            with patch("pcbai.tools.engine.atomic_write", side_effect=lambda p, data: atomic_write(p, bad)):
                output = self.engine.call(tool, dict(target, mode="apply", candidate_id=preview["candidate_id"]))
            self.assertFalse(output["ok"], output)
            self.assertEqual(output["verified"], "readback_mismatch", output)
            self.assertEqual(output["error"]["code"], "readback_mismatch")
            self.assertEqual(path.read_bytes(), bad)
            self.assertEqual(output["suggested_restore"]["arguments"]["checkpoint_id"], output["checkpoint"]["id"])
            self.assertEqual(output["findings"][0]["source"], "readback")
            if tool != "restore_checkpoint":
                self.assertTrue(any(m["check"] not in {"sha256", "stable_read"} for m in output["readback"]["mismatches"]), output)
        else:
            output = self.engine.call(tool, dict(target, mode="apply", candidate_id=preview["candidate_id"]))
            self.assertTrue(output["ok"], output)
            self.assertEqual(output["readback"]["mismatches"], [], output)
            self.assertEqual(path.read_bytes(), expected)
        self.assertTrue(output["changed"], output)
        self.assertIn("sha256", output["readback"]["checked"])
        self.assertTrue(output["checkpoint"]["id"])
        evidence = json.loads((self.engine.evidence.root / (output["change_id"] + ".json")).read_text(encoding="utf-8"))
        self.assertEqual(evidence["report"]["readback"], output["readback"])
        return output

    def test_sha_ok_but_intent_wrong(self):
        target, preview = self.prepare("set_value")
        candidate = self.engine.candidates[preview["candidate_id"]]
        candidate["data"] = candidate["data"].replace(b'"4k7"', b'"9k9"')
        output = self.engine.call("set_value", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        self.assertFalse(output["ok"], output)
        self.assertNotIn("sha256", [m["check"] for m in output["readback"]["mismatches"]])
        self.assertTrue(any(m["check"].startswith("value:") for m in output["readback"]["mismatches"]))
        self.assertEqual(digest((self.project / target["document"]).read_bytes()), digest(candidate["data"]))

    def test_add_symbol_sha_ok_but_value_wrong(self):
        target, preview = self.prepare("add_symbol")
        candidate = self.engine.candidates[preview["candidate_id"]]
        candidate["data"] = candidate["data"].replace(b'"4k7"', b'"9k9"')
        output = self.engine.call("add_symbol", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        self.assertFalse(output["ok"], output)
        self.assertTrue(any(m["check"].startswith("value:") for m in output["readback"]["mismatches"]))
        self.assertFalse(any(m["check"] == "sha256" for m in output["readback"]["mismatches"]))

    def test_restore_sha_ok_but_wrong_checkpoint_bytes(self):
        target, preview = self.prepare("restore_checkpoint")
        candidate = self.engine.candidates[preview["candidate_id"]]
        candidate["data"] += b" \n"
        output = self.engine.call("restore_checkpoint", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        self.assertFalse(output["ok"], output)
        self.assertEqual([m["check"] for m in output["readback"]["mismatches"]], ["checkpoint_sha256"])

    def test_saved_netlist_unavailable_is_mismatch(self):
        target, preview = self.prepare("connect")
        with patch("pcbai.tools.engine.export_netlist", side_effect=RuntimeError("netlist unavailable")):
            output = self.engine.call("connect", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        self.assertFalse(output["ok"], output)
        self.assertTrue(output["changed"])
        self.assertEqual(output["verified"], "readback_mismatch")

    def test_connect_sha_ok_but_extra_member_is_mismatch(self):
        from pcbai.sch.edit import endpoint, plan_labels
        target, preview = self.prepare("connect")
        candidate = self.engine.candidates[preview["candidate_id"]]
        context = hierarchy(self.session, target["document"])
        anchor = endpoint(candidate["data"], dict(reference="R2", pin="2"), context)["at"]
        candidate["data"] = plan_labels(candidate["data"], dict(name="LINK", x_mm=anchor[0], y_mm=anchor[1]), context)["data"]
        output = self.engine.call("connect", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        self.assertFalse(output["ok"], output)
        self.assertTrue(any(m["check"].startswith("net_members:") for m in output["readback"]["mismatches"]))
        self.assertFalse(any(m["check"] == "sha256" for m in output["readback"]["mismatches"]))

    def test_written_document_disappears_keeps_checkpoint_and_evidence(self):
        target, preview = self.prepare("set_value")
        def disappear(path, data):
            atomic_write(path, data)
            path.unlink()
        with patch("pcbai.tools.engine.atomic_write", side_effect=disappear):
            output = self.engine.call("set_value", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        self.assertFalse(output["ok"], output)
        self.assertTrue(output["changed"], output)
        self.assertTrue(output["checkpoint"]["id"])
        self.assertTrue(output["change_id"])
        self.assertEqual(output["findings"][0]["source"], "readback")
        self.assertIsNone(output["target"])


def install_tests():
    for tool in TOOLS:
        for corrupt in (False, True):
            def test(self, tool=tool, corrupt=corrupt):
                self.lifecycle(tool, corrupt)
            setattr(ReadbackTests, f"test_{tool}_" + ("mismatch_detected" if corrupt else "readback_ok"), test)


install_tests()
