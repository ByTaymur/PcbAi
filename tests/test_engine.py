import tempfile
import unittest
from subprocess import CompletedProcess
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from pcbai.tools.engine import Engine
from tests.helpers import SCHEMATIC, make_project, shared_schematic
from pcbai.kicad.files import write_lock


CLEAN = dict(errors=0, warning_count=0, findings=[], report={"sheets": []}, clean=True)


class EngineTests(unittest.TestCase):
    def setUp(self):
        # Synthetic projects must not depend on another user's open GUI. The real
        # process guard is tested in test_files, and CLI edit tests retain it.
        process_list = patch("pcbai.kicad.files.run", return_value=CompletedProcess([], 0, "", ""))
        process_list.start()
        self.addCleanup(process_list.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = make_project(self.root / "project")
        state = self.root / "state"
        state.mkdir()
        self.engine = Engine([self.project], state)
        self.session = next(iter(self.engine.sessions.entries))
        self.document = "Test.kicad_sch"
        self.base = self.engine.sessions.get(self.session).target(self.document)

    def preview(self, **extra):
        return self.engine.call("set_value", dict(self.base, mode="preview", reference="R1", value="4k7", **extra))

    def apply(self, candidate):
        return self.engine.call("set_value", dict(self.base, mode="apply", candidate_id=candidate))

    def test_ambiguous_sessions_are_never_auto_selected(self):
        second = make_project(self.root / "other")
        engine = Engine([self.project, second], self.root / "state")
        status = engine.call("pcbai_status", {})
        self.assertEqual(len(status["sessions"]), 2)
        self.assertFalse(engine.call("project_summary", {})["ok"])
        self.assertFalse(engine.call("project_summary", {"session": "guess"})["ok"])

    def test_arguments_strictly_validated(self):
        for args in [dict(session=self.session, executable="evil"), {"session": 3}, None, []]:
            output = self.engine.call("project_summary", args)
            self.assertFalse(output["ok"])
            self.assertEqual(output["error"]["code"], "invalid_arguments")

    def test_preview_never_changes_document(self):
        preview = self.preview()
        self.assertTrue(preview["ok"])
        self.assertFalse(preview["changed"])
        self.assertEqual((self.project.parent / self.document).read_bytes(), SCHEMATIC)
        self.assertEqual(self.engine.history.list(self.session), [])

    def test_apply_without_preview_rejected(self):
        self.assertFalse(self.apply("invented")["ok"])

    @patch("pcbai.tools.engine.rule_check", return_value=CLEAN)
    def test_apply_and_restore_roundtrip_with_checkpoint_and_evidence(self, check):
        preview = self.preview()
        applied = self.apply(preview["candidate_id"])
        self.assertTrue(applied["ok"])
        self.assertTrue(applied["changed"])
        self.assertEqual(applied["verified"], "erc_ok")
        self.assertEqual(check.call_count, 2)
        self.assertTrue(applied["measurements"][0]["id"].startswith("ev-"))
        restore = self.engine.call("restore_checkpoint", dict(applied["target"], mode="preview",
                                   checkpoint_id=applied["checkpoint"]["id"]))
        restored = self.engine.call("restore_checkpoint", dict(applied["target"], mode="apply",
                                    candidate_id=restore["candidate_id"]))
        self.assertTrue(restored["changed"])
        self.assertEqual((self.project.parent / self.document).read_bytes(), SCHEMATIC)

    def test_changed_board_invalidates_schematic_preview(self):
        preview = self.preview()
        board = self.project.parent / "Test.kicad_pcb"
        board.write_bytes(board.read_bytes() + b"\n")
        output = self.apply(preview["candidate_id"])
        self.assertEqual(output["error"]["code"], "stale_revision")
        self.assertEqual((self.project.parent / self.document).read_bytes(), SCHEMATIC)

    def test_editor_lock_and_write_lock_reject_mutation(self):
        lock = self.project.parent / "~Test.kicad_sch.lck"
        lock.write_text("busy")
        self.assertEqual(self.preview()["error"]["code"], "editor_open")
        lock.unlink()
        preview = self.preview()
        with write_lock(self.project.parent, self.engine.state):
            self.assertEqual(self.apply(preview["candidate_id"])["error"]["code"], "project_busy")

    def test_no_paths_outside_registered_project(self):
        outside = self.root / "Outside.kicad_sch"
        outside.write_bytes(SCHEMATIC)
        for path in ["../Outside.kicad_sch", str(outside)]:
            output = self.engine.call("list_symbols", {"session": self.session, "document": path})
            self.assertEqual(output["error"]["code"], "outside_project")

    @patch("pcbai.tools.engine.rule_check", side_effect=RuntimeError("simulated crash"))
    def test_preflight_failure_preserves_original(self, _check):
        preview = self.preview()
        output = self.apply(preview["candidate_id"])
        self.assertFalse(output["ok"])
        self.assertEqual((self.project.parent / self.document).read_bytes(), SCHEMATIC)

    @patch("pcbai.tools.engine.rule_check", side_effect=[CLEAN, RuntimeError("post-check failure")])
    def test_post_check_failure_reports_changed_unverified_with_checkpoint(self, _check):
        applied = self.apply(self.preview()["candidate_id"])
        self.assertTrue(applied["changed"])
        self.assertEqual(applied["verified"], "verification_failed")
        self.assertTrue(applied["checkpoint"]["id"])

    def test_wrong_document_candidate_and_extra_apply_args_rejected(self):
        preview = self.preview()
        target = self.engine.sessions.get(self.session).target("Test.kicad_pcb")
        output = self.engine.call("set_value", dict(target, mode="apply", candidate_id=preview["candidate_id"]))
        self.assertEqual(output["error"]["code"], "wrong_target")
        output = self.engine.call("set_value", dict(self.base, mode="apply", candidate_id=preview["candidate_id"],
                                                    value="1k"))
        self.assertEqual(output["error"]["code"], "invalid_arguments")

    @patch("pcbai.tools.engine.rule_check", return_value=CLEAN)
    def test_concurrent_edits_on_same_revision_only_one_can_apply(self, _check):
        first = self.preview()
        second = self.engine.call("set_value", dict(self.base, mode="preview", reference="R1", value="22k"))
        with ThreadPoolExecutor(max_workers=2) as pool:
            outputs = list(pool.map(self.apply, [first["candidate_id"], second["candidate_id"]]))
        self.assertEqual(sum(o["changed"] for o in outputs), 1)
        failure = next(o for o in outputs if not o["ok"])
        self.assertEqual(failure["error"]["code"], "stale_revision")

    def shared_preview(self, value="47k"):
        (self.project.parent / self.document).write_bytes(shared_schematic())
        self.base = self.engine.sessions.get(self.session).target(self.document)
        return self.engine.call("set_value", dict(self.base, mode="preview", reference="R303", value=value))

    @patch("pcbai.tools.engine.rule_check", return_value=CLEAN)
    def test_shared_preview_list_summary_and_apply_disclose_all_impacts(self, _check):
        preview = self.shared_preview()
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(preview["affected_references"], ["R203", "R303"])
        self.assertIn("R203, R303", preview["summary"])
        self.assertTrue(preview["warnings"])
        target = {"session": self.session, "document": self.document}
        listed = self.engine.call("list_symbols", target)
        self.assertEqual([s["Reference"] for s in listed["symbols"]], ["R203", "R303"])
        summary = self.engine.call("project_summary", {"session": self.session})
        self.assertEqual(next(d["item_count"] for d in summary["documents"] if d["kind"] == "sch"), 2)
        applied = self.apply(preview["candidate_id"])
        self.assertTrue(applied["changed"], applied)
        self.assertEqual(applied["affected_instances"], preview["affected_instances"])
        self.assertEqual(applied["warnings"], preview["warnings"])
        self.assertFalse((self.project.parent / ".pcbai-write.lock").exists())
        self.assertEqual(len(list((self.engine.state / "locks").glob("*.lock"))), 1)

    @patch("pcbai.tools.engine.rule_check", side_effect=[CLEAN, RuntimeError("post-check failure")])
    def test_shared_impacts_survive_verification_failure(self, _check):
        applied = self.apply(self.shared_preview()["candidate_id"])
        self.assertEqual(applied["verified"], "verification_failed")
        self.assertEqual(applied["affected_references"], ["R203", "R303"])
        self.assertEqual(len(applied["warnings"]), 2)

    def test_shared_noop_retains_warning_and_creates_no_checkpoint(self):
        output = self.apply(self.shared_preview("10k")["candidate_id"])
        self.assertTrue(output["ok"], output)
        self.assertFalse(output["changed"])
        self.assertEqual(output["affected_references"], ["R203", "R303"])
        self.assertTrue(output["warnings"])
        self.assertEqual(self.engine.history.list(self.session), [])

    def test_invalid_value_creates_no_candidate_or_write(self):
        for value in ["x\ny", "x\ry", "x\ty", "x\x7fy", "x\x85y", "x\ud800y"]:
            output = self.engine.call("set_value", dict(self.base, mode="preview", reference="R1", value=value))
            self.assertEqual(output["error"]["code"], "invalid_arguments", output)
        self.assertEqual(self.engine.candidates, {})
        self.assertEqual((self.project.parent / self.document).read_bytes(), SCHEMATIC)

    def test_unnamed_project_resolves_by_registered_root_uuid(self):
        data = shared_schematic().replace(b'(project "Test"', b'(project ""')
        (self.project.parent / self.document).write_bytes(data)
        self.base = self.engine.sessions.get(self.session).target(self.document)
        listed = self.engine.call("list_symbols", {"session": self.session, "document": self.document})
        self.assertEqual([s["Reference"] for s in listed["symbols"]], ["R203", "R303"])
        preview = self.engine.call("set_value", dict(self.base, mode="preview", reference="R303", value="47k"))
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(preview["affected_references"], ["R203", "R303"])
