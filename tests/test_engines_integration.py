"""Opt-in genuine engine integration. Configured engines must pass; no silent downgrade to mock tests."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from pcbai.external import find_kicad_cli
from pcbai.kicad.files import digest
from pcbai.tools.engine import Engine
from scripts.strip_tracks import strip_tracks
from tests.test_pcb_edit import editors_closed
from tests.test_route_engines import BOARD


def routing_fixture():
    data = BOARD.replace(b'(at 10 10 0)', b'(at 5 10 0)').replace(b'pad "1" smd rect', b'pad "1" thru_hole circle')
    data = data.replace(b'(property "Reference" "R1")', b'(property "Reference" "R1" (at 0 -2 0) '
                        b'(layer "F.SilkS") (uuid "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa") '
                        b'(effects (font (size 1 1) (thickness 0.15))))')
    data = data.replace(b'(property "Value" "1k")', b'(property "Value" "1k" (at 0 2 0) '
                        b'(layer "F.Fab") (uuid "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb") '
                        b'(effects (font (size 1 1) (thickness 0.15))))')
    data = data.replace(b'(layers "F.Cu") (net 1 "GND")', b'(drill 0.6) (layers "*.Cu" "*.Mask") (net 1 "GND")')
    second = (b'(footprint "Test" (layer "F.Cu") (at 15 10 0) (uuid "77777777-7777-4777-8777-777777777777") '
              b'(property "Reference" "R2" (at 0 -2 0) (layer "F.SilkS") '
              b'(uuid "cccccccc-cccc-4ccc-8ccc-cccccccccccc") (effects (font (size 1 1) (thickness 0.15)))) '
              b'(property "Value" "test" (at 0 2 0) (layer "F.Fab") '
              b'(uuid "dddddddd-dddd-4ddd-8ddd-dddddddddddd") (effects (font (size 1 1) (thickness 0.15)))) '
              b'(pad "1" thru_hole circle (at 0 0) (size 1 1) (drill 0.6) (layers "*.Cu" "*.Mask") (net 1 "GND") '
              b'(uuid "88888888-8888-4888-8888-888888888888")))')
    return data[:-1] + second + b')'


class EngineIntegrationTests(unittest.TestCase):
    def test_configured_engines_real_process_preview_apply_and_restore(self):
        engines = [n for n in ("freerouting", "tracemaker") if os.environ.get("PCBAI_" + n.upper())]
        if not engines:
            self.skipTest("Configure PCBAI_FREEROUTING and/or PCBAI_TRACEMAKER for real engine acceptance")
        if not editors_closed():
            self.skipTest("Close KiCad editors for real file-mode apply/restore acceptance")
        demo = Path(find_kicad_cli()).parent.parent / "share/kicad/demos/ecc83"
        for name in engines:
            with self.subTest(engine=name), tempfile.TemporaryDirectory(prefix="pcbai-engine-test-") as tmp:
                root = Path(tmp)
                shutil.copytree(demo, root / "project")
                project = root / "project/ecc83-pp.kicad_pro"
                pcb = project.with_suffix(".kicad_pcb")
                original_demo = digest((demo / pcb.name).read_bytes())
                # Owned minimal routing fixture verifies the transaction independently of motor quality on demos.
                original = routing_fixture()
                pcb.write_bytes(original)
                state = root / "state"
                state.mkdir()
                engine = Engine([project], state)
                session = next(iter(engine.sessions.entries.values()))
                target = session.target(pcb.name)
                options = dict(work=3000000, threads=1, variants=1) if name == "tracemaker" else dict(passes=5, threads=1)
                preview = engine.call("autoroute", dict(target, mode="preview", engine=name, options=options,
                                                       timeout_seconds=120))
                self.assertTrue(preview["ok"], preview)
                self.assertEqual(preview["blockers"], [], preview.get("new_findings"))
                self.assertEqual(preview["engine_metrics"]["unconnected_after"], 0)
                self.assertEqual(preview["new_findings"], [])
                rendered = engine.call("engine_preview", dict(target, candidate_id=preview["candidate_id"]))
                self.assertTrue(rendered["ok"], rendered)
                self.assertTrue(rendered["before"]["layers"])
                self.assertTrue(rendered["after"]["layers"])
                applied = engine.call("autoroute", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
                self.assertTrue(applied["ok"], applied)
                self.assertTrue(applied["change_id"])
                restore = engine.call("restore_checkpoint", dict(session.target(pcb.name), mode="preview",
                                     checkpoint_id=applied["checkpoint"]["id"]))
                done = engine.call("restore_checkpoint", dict(session.target(pcb.name), mode="apply",
                                  candidate_id=restore["candidate_id"]))
                self.assertTrue(done["ok"], done)
                self.assertEqual(pcb.read_bytes(), original)
                self.assertEqual(digest((demo / pcb.name).read_bytes()), original_demo)
                engine.jobs.close()

    def test_ecc83_demo_new_errors_are_rejected_without_writing(self):
        if not os.environ.get("PCBAI_FREEROUTING"):
            self.skipTest("Configure PCBAI_FREEROUTING for genuine demo engine safety test")
        if not editors_closed():
            self.skipTest("Close KiCad for file-mode engine acceptance")
        demo = Path(find_kicad_cli()).parent.parent / "share/kicad/demos/ecc83"
        with tempfile.TemporaryDirectory(prefix="pcbai-engine-demo-") as tmp:
            root = Path(tmp)
            shutil.copytree(demo, root / "project")
            project = root / "project/ecc83-pp.kicad_pro"
            pcb = project.with_suffix(".kicad_pcb")
            original = strip_tracks(pcb.read_bytes())
            pcb.write_bytes(original)
            state = root / "state"
            state.mkdir()
            engine = Engine([project], state)
            session = next(iter(engine.sessions.entries.values()))
            preview = engine.call("autoroute", dict(session.target(pcb.name), mode="preview", engine="freerouting",
                                   options=dict(passes=5, threads=1), timeout_seconds=120))
            self.assertTrue(preview["ok"], preview)
            self.assertEqual(preview["engine_metrics"]["unconnected_after"], 0)
            # Motor quality is reported separately; this test asserts the safety contract in either outcome.
            applied = engine.call("autoroute", dict(session.target(pcb.name), mode="apply", candidate_id=preview["candidate_id"]))
            if preview["new_findings"]:
                self.assertIn("new_violations", preview["blockers"])
                self.assertEqual(applied["error"]["code"], "new_violations")
                self.assertEqual(pcb.read_bytes(), original)
            else:
                self.assertTrue(applied["ok"], applied)
            engine.jobs.close()
