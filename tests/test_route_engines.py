import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from pcbai.core.contract import PcbAiError
from pcbai.external import find_freerouting, find_tracemaker
from pcbai.pcb.engine_guard import guard, rebase_routes
from pcbai.pcb.engine_metrics import added_errors, outside_footprints, routing, segment_inside
from pcbai.pcb.engines.base import run_process
from pcbai.pcb.engines.tracemaker import build
from pcbai.pcb.engines.wsl import linux_path, parse_spec
from pcbai.pcb.edit import plan_move
from pcbai.tools.engine import Engine
from tests.helpers import make_project

FP = "22222222-2222-4222-8222-222222222222"
VIA = b'(via (at 8 8) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net 1) (uuid "33333333-3333-4333-8333-333333333333"))'
BOARD = (b'(kicad_pcb (version 20241229) (generator "pcbnew")\n'
         b'(layers (0 "F.Cu" signal) (31 "B.Cu" signal) (44 "Edge.Cuts" user))\n'
         b'(net 0 "") (net 1 "GND")\n'
         b'(footprint "R" (layer "F.Cu") (at 10 10 0) (uuid "' + FP.encode() + b'")\n'
         b'(property "Reference" "R1") (property "Value" "1k")\n'
         b'(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net 1 "GND") '
         b'(uuid "44444444-4444-4444-8444-444444444444")))\n'
         b'(gr_rect (start 0 0) (end 20 20) (layer "Edge.Cuts") (stroke (width 0.05) (type default)) '
         b'(uuid "55555555-5555-4555-8555-555555555555")))')


def via_board(data=BOARD):
    return data[:-1] + b'\n' + VIA + b')'


def check(findings=()):
    return dict(errors=sum(f.get("severity") == "error" for f in findings), warning_count=0, findings=list(findings),
                report=dict(violations=list(findings)), clean=not findings)


class GuardTests(unittest.TestCase):
    def test_place_zero_angle_omission_only_at_movable_footprint_position(self):
        moved = plan_move(BOARD, "R1", 11, 10)["data"]
        omitted = moved.replace(b'(at 11 10 0)', b'(at 11 10)')
        self.assertTrue(guard(BOARD, omitted, operation='place')['clean'])
        self.assertTrue(guard(BOARD.replace(b'(at 10 10 0)', b'(at 10 10)'), moved, operation='place')['clean'])
        for changed in (omitted.replace(b'"1k"', b'"2k"'), omitted.replace(b'(net 1 "GND")', b'(net 1 "OTHER")'),
                        omitted.replace(b'(at 0 0)', b'(at 0 0 0)'), omitted.replace(b'(at 11 10)', b'(at 11 10 90)')):
            with self.subTest(changed=changed), self.assertRaises(PcbAiError):
                guard(BOARD, changed, operation='place')
        with self.assertRaises(PcbAiError):
            guard(BOARD, omitted)
        locked = BOARD.replace(b'(footprint "R"', b'(footprint "R" locked')
        with self.assertRaises(PcbAiError):
            guard(locked, omitted, operation='place')

    def test_route_accepts_only_added_copper_and_defined_net(self):
        self.assertTrue(guard(BOARD, via_board())["clean"])
        for changed in (via_board().replace(b'"1k"', b'"9k"'), via_board().replace(b'20241229', b'20260101'),
                        via_board().replace(b'(net 1) (uuid', b'(net 7) (uuid'),
                        via_board().replace(b'33333333-3333-4333-8333-333333333333', FP.encode()),
                        via_board().replace(b'(end 20 20)', b'(end 30 20)')):
            with self.assertRaises(PcbAiError) as raised:
                guard(BOARD, changed)
            self.assertEqual(raised.exception.code, "engine_touched_foreign_items")

    def test_uuid_case_and_dash_variants_cannot_bypass_uniqueness(self):
        key = b'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
        original = BOARD.replace(FP.encode(), key)
        for alias in (key.upper(), key.replace(b'-', b'')):
            with self.assertRaises(PcbAiError):
                guard(original, via_board(original).replace(b'33333333-3333-4333-8333-333333333333', alias))

    def test_uppercase_footprint_uuid_still_reaches_outside_gate(self):
        original = BOARD.replace(FP.encode(), b'AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA')
        changed = plan_move(original, "R1", 30, 30)["data"]
        moved = guard(original, changed, operation="place")["moved"]
        self.assertEqual(outside_footprints(changed, moved)[0]["reference"], "R1")

    def test_zone_outline_protected_but_fill_permitted(self):
        zone = (b'(zone (net 1) (net_name "GND") (layer "F.Cu") '
                b'(uuid "66666666-6666-4666-8666-666666666666") '
                b'(polygon (pts (xy 1 1) (xy 19 1) (xy 19 19)))'
                b'(filled_polygon (layer "F.Cu") (pts (xy 1 1) (xy 2 1) (xy 2 2))))')
        before = BOARD[:-1] + zone + b')'
        after = before.replace(b'(xy 2 2)', b'(xy 3 3)')
        self.assertTrue(guard(before, after)["clean"])
        with self.assertRaises(PcbAiError):
            guard(before, before.replace(b'(xy 19 19)', b'(xy 18 18)'))

    def test_reroute_and_locked_route(self):
        before = via_board()
        with self.assertRaises(PcbAiError):
            guard(before, BOARD)
        self.assertTrue(guard(before, BOARD, reroute=True)["clean"])
        with self.assertRaises(PcbAiError):
            guard(before.replace(b'(via ', b'(via locked '), BOARD, reroute=True)

    def test_place_move_lock_and_outside(self):
        changed = plan_move(BOARD, "R1", 11, 12)["data"]
        moved = guard(BOARD, changed, operation="place")["moved"]
        self.assertEqual(len(moved), 1)
        self.assertEqual(outside_footprints(changed, moved), [])
        outside = plan_move(BOARD, "R1", 30, 30)["data"]
        moved = guard(BOARD, outside, operation="place")["moved"]
        self.assertEqual(outside_footprints(outside, moved)[0]["reference"], "R1")
        for bad in (changed.replace(b'"1k"', b'"2k"'), changed.replace(b'(net 1 "GND")', b'(net 0 "")')):
            with self.assertRaises(PcbAiError):
                guard(BOARD, bad, operation="place")
        locked = BOARD.replace(b'(footprint "R"', b'(footprint "R" locked')
        with self.assertRaises(PcbAiError):
            guard(locked, plan_move(locked, "R1", 11, 12)["data"], operation="place")

    def test_rebase_preserves_original_headers_and_net_format(self):
        original = BOARD.replace(b'(generator "pcbnew")', b'(generator "original")')
        # KiCad normalized baseline's bytes may differ, but the imported result must preserve that baseline.
        rebased = rebase_routes(original, BOARD, via_board())
        self.assertIn(b'(generator "original")', rebased)
        self.assertTrue(guard(original, rebased)["clean"])
        with self.assertRaises(PcbAiError):
            rebase_routes(original, BOARD, via_board().replace(b'"1k"', b'"2k"'))

    def test_same_error_count_different_violation_is_not_clean(self):
        a = dict(type="clearance", severity="error", group="violations", items=[dict(uuid="a", pos=dict(x=1, y=2))])
        b = dict(a, type="shorting_items")
        self.assertEqual(added_errors(check([a]), check([b])), [b])
        self.assertEqual(added_errors(check([a]), check([a])), [])
        self.assertEqual(routing(via_board())["via_count"], 1)

    def test_narrow_concave_notch_and_board_hole_are_detected(self):
        outline = [[0, 0], [10, 0], [10, 10], [4, 10], [4, 5], [3, 5], [3, 10], [0, 10]]
        self.assertFalse(segment_inside([1, 6], [9, 6], [outline]))
        self.assertTrue(segment_inside([1, 4], [9, 4], [outline]))
        hole = [[3, 3], [4, 3], [4, 4], [3, 4]]
        self.assertFalse(segment_inside([1, 3.5], [9, 3.5], [[[0, 0], [10, 0], [10, 10], [0, 10]], hole]))

    def test_bbox_without_courtyard_cannot_enclose_internal_cutout(self):
        changed = plan_move(BOARD.replace(b'(size 1 1)', b'(size 7 7)'), "R1", 5, 5)["data"]
        hole = b'(gr_rect (start 4.75 1.75) (end 5.25 2.25) (layer "Edge.Cuts") (stroke (width 0.05) (type default)))'
        changed = changed[:-1] + hole + b')'
        self.assertEqual(outside_footprints(changed, [dict(uuid=FP)])[0]["reference"], "R1")

    def test_courtyard_edges_join_by_endpoint_not_file_order(self):
        courtyard = (b'(fp_line (start -4 -4) (end 4 -4) (layer "F.CrtYd")) '
                     b'(fp_line (start 4 -4) (end 4 4) (layer "F.CrtYd")) '
                     b'(fp_line (start -4 4) (end -4 -4) (layer "F.CrtYd")) '
                     b'(fp_line (start 4 4) (end -4 4) (layer "F.CrtYd")) ')
        changed = plan_move(BOARD.replace(b'(property "Reference"', courtyard + b'(property "Reference"'), "R1", 5, 5)["data"]
        hole = b'(gr_rect (start 4.75 7.75) (end 5.25 8.25) (layer "Edge.Cuts") (stroke (width 0.05) (type default)))'
        changed = changed[:-1] + hole + b')'
        self.assertEqual(outside_footprints(changed, [dict(uuid=FP)])[0]["reference"], "R1")


class ExecutableTests(unittest.TestCase):
    def test_wsl_specs_paths_and_allowlist(self):
        self.assertEqual(parse_spec("wsl:Ubuntu:/opt/tracemaker"), ("Ubuntu", "/opt/tracemaker"))
        self.assertEqual(linux_path("C:\\a b\\x.kicad_pcb"), "/mnt/c/a b/x.kicad_pcb")
        for path in ("wsl:Ubuntu;sh:/x", "wsl:Ubuntu:/opt/../x", "wsl:Ubuntu:relative"):
            with self.assertRaises(PcbAiError):
                parse_spec(path)
        for path in ("relative", "\\\\server\\share\\x", "C:\\a\\..\\b"):
            with self.assertRaises(PcbAiError):
                linux_path(path)
        with patch("pcbai.pcb.engines.tracemaker.find_tracemaker", return_value="/bin/tm"):
            command, deterministic = build("route", "in", "out", {"work": 500}, 150)
            self.assertTrue(deterministic)
            self.assertIn("--no-gpu", command)
            for options in ({"config": "bad"}, {"view": True}, {"work": 1, "time_seconds": 1}):
                with self.assertRaises(PcbAiError):
                    build("route", "in", "out", options, 150)

    def test_bad_explicit_configuration_does_not_fall_back_to_path(self):
        with patch.dict(os.environ, {"PCBAI_FREEROUTING": "/no/such/file", "PCBAI_TRACEMAKER": "wsl:bad:/../x"}):
            with self.assertRaises(PcbAiError):
                find_freerouting()
            with self.assertRaises(PcbAiError):
                find_tracemaker()

    def test_timeout_kills_descendants_and_no_later_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "survived"
            child_code = "import time; from pathlib import Path; time.sleep(2); Path(" + repr(str(marker)) + ").write_text('bad')"
            parent_code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c'," + repr(child_code) + "]); time.sleep(30)"
            with self.assertRaises(PcbAiError) as raised:
                run_process([sys.executable, "-c", parent_code], cwd=tmp, timeout=0.3)
            self.assertEqual(raised.exception.code, "timeout")
            time.sleep(2.2)
            self.assertFalse(marker.exists())

    def test_output_tail_bounded_and_shell_text_is_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_process([sys.executable, "-c", "import sys; print('x'*10000); print(sys.argv[1])", "$(bad); &"],
                              cwd=tmp, timeout=5)
            self.assertEqual(out["returncode"], 0)
            self.assertLessEqual(len(out["stdout_tail"]), 4096)
            self.assertIn("$(bad); &", out["stdout_tail"])


class EngineFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.project = make_project(root / "project")
        self.board = self.project.with_suffix(".kicad_pcb")
        self.board.write_bytes(BOARD)
        state = root / "state"
        state.mkdir()
        self.engine = Engine([self.project], state)
        self.session = next(iter(self.engine.sessions.entries.values()))
        self.closed = patch("pcbai.tools.engine.assert_closed")
        self.closed.start()
        self.rule = patch("pcbai.tools.engine.rule_check", return_value=check())
        self.rule.start()
        self.external = patch("pcbai.tools.engine.execute_engine", return_value=(via_board(), dict(
            engine="tracemaker", deterministic=True, input_sha256="fake", output_sha256="fake", argv=[])))
        self.external.start()

    def tearDown(self):
        self.engine.jobs.close()
        self.external.stop()
        self.rule.stop()
        self.closed.stop()
        self.tmp.cleanup()

    def target(self):
        return self.session.target(self.board.name)

    def preview(self, **args):
        return self.engine.call("autoroute", dict(self.target(), mode="preview", engine="tracemaker", **args))

    def test_preview_apply_checkpoint_and_byte_equal_restore(self):
        target = self.target()
        preview = self.preview()
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(self.board.read_bytes(), BOARD)
        self.assertEqual(preview["engine_metrics"]["after"]["via_count"], 1)
        apply = self.engine.call("autoroute", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        self.assertTrue(apply["ok"], apply)
        self.assertTrue(apply["change_id"])
        restored = self.engine.call("restore_checkpoint", dict(self.target(), mode="preview",
                                    checkpoint_id=apply["checkpoint"]["id"]))
        final = self.engine.call("restore_checkpoint", dict(self.target(), mode="apply",
                                candidate_id=restored["candidate_id"]))
        self.assertTrue(final["ok"], final)
        self.assertEqual(self.board.read_bytes(), BOARD)

    def test_stale_revision_and_new_apply_arguments_rejected(self):
        target = self.target()
        preview = self.preview()
        response = self.engine.call("autoroute", dict(target, mode="apply", engine="tracemaker",
                                    candidate_id=preview["candidate_id"]))
        self.assertEqual(response["error"]["code"], "invalid_arguments")
        self.project.write_text('{"changed": true}')
        response = self.engine.call("autoroute", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        self.assertEqual(response["error"]["code"], "stale_revision")
        self.assertEqual(self.board.read_bytes(), BOARD)

    def test_jobs_preview_only_and_candidate_returned(self):
        target = self.target()
        missing = self.engine.call("start_job", dict(target, tool="autoroute", engine="tracemaker"))
        self.assertFalse(missing["ok"])
        denied = self.engine.call("start_job", dict(target, tool="autoroute", mode="apply", engine="tracemaker"))
        self.assertFalse(denied["ok"])
        job = self.engine.call("start_job", dict(target, tool="autoroute", mode="preview", engine="tracemaker"))
        self.engine.jobs.close()
        polled = self.engine.call("job_status", dict(job_id=job["job"]["job_id"]))
        self.assertEqual(polled["job"]["status"], "completed", polled)
        self.assertTrue(polled["job"]["result"]["candidate_id"])

    def test_real_fake_engine_process_drives_route_and_place_candidates(self):
        self.external.stop()
        fixture = Path(__file__).parent / "fixtures/fake_engine.py"

        def build_fake(operation, source, destination, options, timeout, **kwargs):
            return [sys.executable, str(fixture.resolve()), operation, str(source), "-o", str(destination)], True

        with patch("pcbai.pcb.engines.tracemaker.build", side_effect=build_fake), patch(
                "pcbai.pcb.engines.describe", return_value=[dict(engine="tracemaker", version="fixture")]):
            route = self.preview()
            self.assertTrue(route["ok"], route)
            self.assertEqual(route["engine_run"]["returncode"], 0)
            place = self.engine.call("autoplace", dict(self.target(), mode="preview", engine="tracemaker"))
            self.assertTrue(place["ok"], place)
            self.assertEqual(place["engine_metrics"]["moved_count"], 1)
        self.external.start()

    def test_same_count_new_drc_blocks_apply(self):
        a = dict(type="clearance", severity="error", group="violations", items=[])
        b = dict(a, type="shorting_items")
        self.rule.stop()
        self.rule = patch("pcbai.tools.engine.rule_check", side_effect=[check([a]), check([b]), check([b])])
        self.rule.start()
        preview = self.preview()
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(preview["blockers"], ["new_violations"])
        applied = self.engine.call("autoroute", dict(self.target(), mode="apply", candidate_id=preview["candidate_id"]))
        self.assertEqual(applied["error"]["code"], "new_violations")
        self.assertEqual(self.board.read_bytes(), BOARD)


if __name__ == "__main__":
    unittest.main()
