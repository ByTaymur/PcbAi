import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pcbai.core.contract import PcbAiError
from pcbai.fab.profile import IDS, KEYS, check, describe, load, read_settings, tighten
from pcbai.kicad.files import revision
from pcbai.tools.engine import Engine
from tests.helpers import make_project


class FabProfilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = make_project(self.root / "project")

    def test_attributed_bundled_profiles_and_path_rejection(self):
        profiles = describe()
        self.assertEqual([p["id"] for p in profiles], list(IDS))
        for profile in profiles:
            self.assertEqual(profile["qualifier"], "üreticiyle doğrulayın")
            self.assertEqual(len(profile["sha256"]), 64)
            for row in profile["minimums"].values():
                self.assertTrue(row["source_url"])
                self.assertEqual(row["retrieved"], "2026-10-14")
        for identity in ("../generic", "https://evil/profile", "GENERIC"):
            with self.assertRaises(PcbAiError):
                load(identity)

    def test_missing_saved_fields_use_measured_defaults_not_zero(self):
        settings = read_settings(self.project)
        output = tighten(settings, load("jlcpcb-2l"), dict.fromkeys(KEYS, .5))
        self.assertEqual(output["min_copper_edge_clearance"]["effective_mm"], .5)
        self.assertEqual(output["min_track_width"]["effective_mm"], .5)
        self.assertEqual(output["min_text_height"]["effective_mm"], 1)
        with self.assertRaises(PcbAiError) as raised:
            tighten(read_settings(self.project), load("jlcpcb-2l"), {})
        self.assertEqual(raised.exception.code, "profile_defaults_unavailable")

    def test_override_cannot_loosen_saved_native_or_profile_minima(self):
        settings = read_settings(self.project)
        settings["board"]["design_settings"]["rules"]["min_clearance"] = .8
        for overrides in ({"min_clearance": .7}, {"min_text_height": .9}, {"min_track_width": .1}):
            with self.assertRaises(PcbAiError) as raised:
                tighten(copy.deepcopy(settings), load("jlcpcb-2l"), dict.fromkeys(KEYS, .5), overrides)
            self.assertEqual(raised.exception.code, "profile_loosening")
        output = tighten(settings, load("jlcpcb-2l"), dict.fromkeys(KEYS, .5), {"min_clearance": 1})
        self.assertEqual(output["min_clearance"]["effective_mm"], 1)

    def test_untrusted_settings_and_override_values_rejected(self):
        for raw in ('[]', '{"board": []}', '{"board":{},"board":{}}', '{"a":NaN}'):
            self.project.write_text(raw)
            with self.assertRaises(PcbAiError):
                read_settings(self.project)
        self.project.write_text('{}')
        for bad in (True, float("nan"), float("inf"), -1, 26, "1mm"):
            with self.assertRaises(PcbAiError):
                tighten(read_settings(self.project), load("generic"), dict.fromkeys(KEYS, .5), {"min_track_width": bad})

    def test_strict_copy_promotes_native_ignored_rules_preserves_original(self):
        self.project.with_suffix(".kicad_pcb").write_bytes(b'(kicad_pcb (layers (0 "F.Cu" signal) (2 "B.Cu" signal)))')
        before = revision(self.project.parent)
        calls = []

        def oracle(root, document, kind, **kwargs):
            calls.append(json.loads((root / "Test.kicad_pro").read_text()))
            ignored = [dict(rule="track_width", required=True, sources=["native"])] if len(calls) == 1 else []
            return dict(findings=[dict(type="track_width", severity="error", items=[])], ignored_rules=ignored,
                        inputs_sha256={"Test.kicad_pro": "native-input"}, clean=False, errors=1,
                        warning_count=0, excluded_count=0)

        with patch("pcbai.fab.profile.rule_check", side_effect=oracle):
            output = check(self.project.parent, "Test.kicad_pcb", before, "jlcpcb-2l",
                           baseline_reader=lambda root, document: dict.fromkeys(KEYS, .5))
        self.assertEqual(calls[1]["board"]["design_settings"]["rules"]["min_track_width"], .5)
        self.assertEqual(calls[1]["board"]["design_settings"]["rule_severities"]["track_width"], "error")
        self.assertEqual(output["findings"][0]["source"], "fab_profile")
        self.assertEqual(revision(self.project.parent), before)
        with self.assertRaises(PcbAiError):
            check(self.project.parent, "Test.kicad_pcb", before, "jlcpcb-4l")

    def test_engine_profiles_readonly_and_failure_manifest(self):
        (self.root / "state").mkdir()
        engine = Engine([self.project], self.root / "state")
        self.assertTrue(engine.call("fab_profiles", {})["ok"])
        session = next(iter(engine.sessions.entries))
        output = engine.call("check_fab_profile", dict(session=session, document="Test.kicad_pcb",
                            revision=revision(self.project.parent), profile="../bad"))
        self.assertFalse(output["ok"])
        self.assertEqual(output["verified"], "checks_incomplete")

    def test_unknown_ignored_rule_remains_incomplete(self):
        self.project.with_suffix(".kicad_pcb").write_bytes(b'(kicad_pcb (layers (0 "F.Cu" signal) (2 "B.Cu" signal)))')
        self.project.write_text(json.dumps(dict(board=dict(design_settings=dict(rule_severities={"future_unknown": "ignore"})))))
        oracle = dict(findings=[], ignored_rules=[dict(rule="future_unknown", required=True, sources=["project"])],
                      inputs_sha256={}, clean=False, errors=0, warning_count=0, excluded_count=0)
        with patch("pcbai.fab.profile.rule_check", return_value=oracle):
            output = check(self.project.parent, "Test.kicad_pcb", revision(self.project.parent), "generic")
        self.assertEqual(output["promoted_rules"], [])
        self.assertFalse(output["clean"])

    def test_profile_export_blocks_before_output_on_failed_check(self):
        from pcbai.kicad.exports import export_fab
        destination = self.root / "fabrication.zip"
        with patch("pcbai.fab.profile.check_copy", return_value=dict(clean=False, findings=[], ignored_rules=["unknown"])):
            with self.assertRaises(PcbAiError) as raised:
                export_fab(self.project.parent, "Test.kicad_pcb", destination, revision(self.project.parent), profile="generic")
        self.assertEqual(raised.exception.code, "fab_profile_blocked")
        self.assertFalse(destination.exists())


class NativeFabProfilesTests(unittest.TestCase):
    def test_same_synthetic_demo_generic_clean_strict_findings_without_source_writes(self):
        from pcbai.external import find_kicad_cli, find_kicad_python, private_kicad_config, run
        from pcbai.fab.settings import native_defaults
        import os
        try:
            python, cli = find_kicad_python(), find_kicad_cli()
        except PcbAiError as exc:
            self.skipTest(str(exc))
        with tempfile.TemporaryDirectory(prefix="pcbai-profile-acceptance-") as temporary:
            root = Path(temporary)
            project = root / "Demo.kicad_pro"
            project.write_text('{}')
            # Trusted script creates a disposable closed rectangle and a narrow, netless track.
            script = '''import pcbnew,sys,os
b=pcbnew.BOARD()
for a,z in [((0,0),(20,0)),((20,0),(20,20)),((20,20),(0,20)),((0,20),(0,0))]:
 s=pcbnew.PCB_SHAPE();s.SetShape(pcbnew.SHAPE_T_SEGMENT);s.SetLayer(pcbnew.Edge_Cuts)
 s.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(a[0]),pcbnew.FromMM(a[1])))
 s.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(z[0]),pcbnew.FromMM(z[1])));s.SetWidth(pcbnew.FromMM(.05));b.Add(s)
for a,z in [((5,5),(10,5)),((10,5),(10,10)),((10,10),(5,10)),((5,10),(5,5))]:
 t=pcbnew.PCB_TRACK(b);t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(a[0]),pcbnew.FromMM(a[1])))
 t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(z[0]),pcbnew.FromMM(z[1])));t.SetWidth(pcbnew.FromMM(.3));t.SetLayer(pcbnew.F_Cu);b.Add(t)
pcbnew.SaveBoard(sys.argv[1],b);os._exit(0)
'''
            helper = root / "create.py"
            helper.write_text(script)
            private = private_kicad_config(cli, root / "private-config")
            process = run([python, helper, root / "Demo.kicad_pcb"], cwd=root, timeout=30,
                          env=dict(os.environ, KICAD_CONFIG_HOME=str(private)))
            self.assertEqual(process.returncode, 0, process.stderr)
            before = revision(root)
            baseline = native_defaults(root, "Demo.kicad_pcb")
            self.assertGreater(baseline["min_track_width"], 0)
            generic = check(root, "Demo.kicad_pcb", before, "generic")
            self.assertTrue(generic["clean"], generic["findings"])
            strict = check(root, "Demo.kicad_pcb", before, "generic", overrides={"min_track_width": .6})
            self.assertTrue(any(row["rule_id"] == "track_width" for row in strict["findings"]), strict)
            self.assertFalse(strict["clean"])
            self.assertEqual(revision(root), before)
            self.assertEqual(strict["effective_minimums"]["min_track_width"]["effective_mm"], .6)
