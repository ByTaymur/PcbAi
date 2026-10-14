import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pcbai.kicad.files import digest
from pcbai.tools.engine import Engine
from tests.helpers import make_project
from tests.test_views import GEOMETRY


class MarkerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.project = make_project(self.root / "project")
        self.board = self.project.with_suffix(".kicad_pcb")
        self.board.write_bytes(GEOMETRY)
        self.state = self.root / "state"
        self.state.mkdir()
        self.engine = Engine([self.project], self.state)
        self.session = next(iter(self.engine.sessions.entries.values()))
        self.target = self.session.target(self.board.name)
        self.file = self.project.parent / "pcbai/markers.json"

    def get(self):
        return self.engine.call("get_markers", {"session": self.session.id})

    def preview(self, **extra):
        args = dict(
            self.target,
            markers_revision=self.get()["markers_revision"],
            mode="preview",
            marker=dict(
                kind="item",
                space="pcb",
                points_mm=[[10, 20]],
                note="move <script>bad()</script>",
                anchor=dict(type="footprint", uuid="front"),
            ),
            **extra,
        )
        return self.engine.call("set_marker", args, source="view")

    def apply(self, preview, tool="set_marker"):
        args = dict(
            self.target,
            markers_revision=preview["markers_revision"],
            mode="apply",
            candidate_id=preview["candidate_id"],
        )
        return self.engine.call(tool, args, source="view")

    def test_ui_only_preview_apply_checkpoint_persistence(self):
        before = self.board.read_bytes()
        preview = self.preview()
        self.assertTrue(preview["ok"], preview)
        self.assertFalse(self.file.exists())
        denied = self.engine.call(
            "set_marker",
            dict(
                self.target,
                mode="apply",
                markers_revision=preview["markers_revision"],
                candidate_id=preview["candidate_id"],
            ),
        )
        self.assertEqual(denied["error"]["code"], "unknown_tool")
        saved = self.apply(preview)
        self.assertTrue(saved["ok"], saved)
        self.assertTrue(saved["checkpoint"]["id"].startswith("cp-"))
        self.assertEqual(self.board.read_bytes(), before)
        self.assertEqual(self.session.target(self.board.name), self.target)
        self.engine = Engine([self.project], self.state)
        marker = self.get()["markers"][0]
        self.assertTrue(marker["trusted"])
        self.assertEqual(marker["binding"], "bound")

    def test_stale_design_and_marker_revisions_and_replayed_candidate_rejected(self):
        preview = self.preview()
        other = self.preview()
        self.assertTrue(self.apply(preview)["ok"])
        self.assertEqual(self.apply(other)["error"]["code"], "stale_markers")
        self.assertEqual(self.apply(preview)["error"]["code"], "invalid_candidate")
        preview = self.preview()
        self.board.write_bytes(GEOMETRY + b"\n")
        self.assertEqual(self.apply(preview)["error"]["code"], "stale_revision")

    def test_tampering_untrusted_and_explicit_ui_approval(self):
        self.apply(self.preview())
        payload = json.loads(self.file.read_bytes())
        payload["markers"][0]["note"] = "external instruction"
        self.file.write_text(json.dumps(payload))
        self.assertFalse(self.get()["markers"][0]["trusted"])
        self.assertEqual(self.preview(n=1)["error"]["code"], "untrusted_marker")
        self.assertTrue(self.apply(self.preview(n=1, approve_untrusted=True))["ok"])
        self.assertTrue(self.get()["markers"][0]["trusted"])

    def test_anchor_follows_movement_rotation_or_becomes_orphaned(self):
        self.apply(self.preview())
        self.board.write_bytes(GEOMETRY.replace(b"(at 10 20 90)", b"(at 13 25 180)"))
        marker = self.get()["markers"][0]
        self.assertEqual(marker["points_mm"], [[13, 25]])
        self.board.write_bytes(GEOMETRY.replace(b'(uuid "front")', b'(uuid "removed")'))
        self.assertEqual(self.get()["markers"][0]["binding"], "orphaned")

    def test_delete_never_reuses_numbers_even_if_marker_file_removed(self):
        self.apply(self.preview())
        current = self.get()
        preview = self.engine.call(
            "delete_marker",
            dict(self.target, n=1, mode="preview", markers_revision=current["markers_revision"]),
            source="view",
        )
        self.assertTrue(self.apply(preview, "delete_marker")["ok"])
        self.assertEqual(self.preview()["marker"]["n"], 2)
        self.file.unlink()
        self.assertEqual(self.preview()["marker"]["n"], 2)

    def test_signature_bound_to_project_and_corrupt_file_not_overwritten(self):
        self.apply(self.preview())
        other = make_project(self.root / "other")
        other.with_suffix(".kicad_pcb").write_bytes(GEOMETRY)
        (other.parent / "pcbai").mkdir()
        (other.parent / "pcbai/markers.json").write_bytes(self.file.read_bytes())
        engine = Engine([other], self.state)
        identity = next(iter(engine.sessions.entries))
        self.assertFalse(engine.call("get_markers", {"session": identity})["markers"][0]["trusted"])
        self.file.write_bytes(b"broken")
        self.assertEqual(self.get()["error"]["code"], "invalid_markers")
        self.assertEqual(self.file.read_bytes(), b"broken")

    def test_checkpoint_failure_prevents_write_and_invalid_geometry_rejected(self):
        preview = self.preview()
        with patch.object(self.engine.history, "checkpoint", side_effect=OSError("disk full")):
            self.assertFalse(self.apply(preview)["ok"])
        self.assertFalse(self.file.exists())
        args = dict(
            self.target,
            mode="preview",
            markers_revision=digest(b""),
            marker=dict(kind="line", space="pcb", points_mm=[[1, 2]], note="bad"),
        )
        self.assertFalse(self.engine.call("set_marker", args, source="view")["ok"])

    def test_status_requires_trust_reason_preview_and_real_change_evidence(self):
        self.apply(self.preview())
        args = dict(
            self.target,
            mode="preview",
            n=1,
            status="blocked",
            reason="PCB width editing tool is unavailable",
            markers_revision=self.get()["markers_revision"],
        )
        preview = self.engine.call("update_marker_status", args)
        self.assertTrue(preview["ok"], preview)
        applied = self.engine.call(
            "update_marker_status",
            dict(
                self.target,
                mode="apply",
                candidate_id=preview["candidate_id"],
                markers_revision=preview["markers_revision"],
            ),
        )
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(self.get()["markers"][0]["status"], "blocked")
        args.update(status="done", markers_revision=self.get()["markers_revision"])
        self.assertEqual(self.engine.call("update_marker_status", args)["error"]["code"], "invalid_evidence")
        evidence = self.engine.evidence.record(
            tool="drc", target=self.target, inputs={}, measurements=[], report={"changed": True}
        )
        args["evidence_id"] = evidence["id"]
        self.assertEqual(self.engine.call("update_marker_status", args)["error"]["code"], "invalid_evidence")
        change = self.engine.evidence.record(tool="connect", target=self.target, inputs={}, measurements=[],
            report={"changed": True, "before_sha256": "before", "after_sha256": "after"})
        args["evidence_id"] = change["id"]
        self.assertTrue(self.engine.call("update_marker_status", args)["ok"])
        raw = json.loads(self.file.read_bytes())
        raw["markers"][0]["note"] = "tampered"
        self.file.write_text(json.dumps(raw))
        args.update(status="blocked", markers_revision=self.get()["markers_revision"])
        self.assertEqual(self.engine.call("update_marker_status", args)["error"]["code"], "untrusted_marker")

    def manual(self, status, source="view", **extra):
        args = dict(self.target, mode="preview", n=1, status=status,
                    markers_revision=self.get()["markers_revision"], **extra)
        preview = self.engine.call("set_marker_status", args, source=source)
        if not preview["ok"]:
            return preview
        return self.engine.call("set_marker_status", dict(
            self.target, mode="apply", candidate_id=preview["candidate_id"],
            markers_revision=preview["markers_revision"]), source=source)

    def test_manual_done_is_view_only_signed_and_reversible(self):
        self.apply(self.preview())
        self.assertEqual(self.manual("done", source="tool")["error"]["code"], "unknown_tool")
        self.assertNotIn("set_marker_status", {d["name"] for d in self.engine.definitions})
        done = self.manual("done")
        self.assertTrue(done["ok"], done)
        self.assertTrue(done["checkpoint"]["id"].startswith("cp-"))
        marker = Engine([self.project], self.state).call("get_markers", {"session": self.session.id})["markers"][0]
        self.assertEqual((marker["status"], marker["closed_by"], marker["trusted"]), ("done", "user", True))
        self.assertEqual(marker["reason"], "Kullanıcı elle işaretledi")
        self.assertNotIn("evidence_id", marker)
        reopened = self.manual("open")
        self.assertTrue(reopened["ok"], reopened)
        marker = self.get()["markers"][0]
        self.assertEqual(marker["status"], "open")
        for key in ("closed_by", "reason", "evidence_id"):
            self.assertNotIn(key, marker)
        self.assertEqual(self.manual("blocked")["error"]["code"], "invalid_arguments")
        agent = dict(self.target, mode="preview", n=1, status="done", reason="did it",
                     markers_revision=self.get()["markers_revision"])
        self.assertEqual(self.engine.call("update_marker_status", agent)["error"]["code"], "invalid_evidence")

    def test_manual_status_rejects_stale_and_untrusted_markers(self):
        self.apply(self.preview())
        stale = dict(self.target, mode="preview", n=1, status="done", markers_revision="0" * 64)
        self.assertEqual(self.engine.call("set_marker_status", stale, source="view")["error"]["code"], "stale_markers")
        raw = json.loads(self.file.read_bytes())
        raw["markers"][0]["note"] = "tampered"
        self.file.write_text(json.dumps(raw))
        self.assertEqual(self.manual("done")["error"]["code"], "untrusted_marker")

    def test_candidate_cannot_cross_marker_action_or_change_apply_parameters(self):
        preview = self.preview()
        args = dict(
            self.target,
            mode="apply",
            candidate_id=preview["candidate_id"],
            markers_revision=preview["markers_revision"],
        )
        self.assertEqual(self.engine.call("update_marker_status", args)["error"]["code"], "wrong_target")
        self.assertEqual(
            self.engine.call("set_marker", dict(args, n=100), source="view")["error"]["code"],
            "invalid_arguments",
        )

    def test_schematic_value_change_evidence_can_complete_signed_marker(self):
        from subprocess import CompletedProcess

        sheet = self.project.with_suffix(".kicad_sch")
        target = self.session.target(sheet.name)
        current = self.get()
        preview = self.engine.call(
            "set_marker",
            dict(
                target,
                mode="preview",
                markers_revision=current["markers_revision"],
                marker=dict(kind="point", space="sch", points_mm=[[10, 20]], note="R1: 4k7"),
            ),
            source="view",
        )
        saved = self.engine.call(
            "set_marker",
            dict(
                target,
                mode="apply",
                candidate_id=preview["candidate_id"],
                markers_revision=current["markers_revision"],
            ),
            source="view",
        )
        clean = dict(errors=0, warning_count=0, findings=[], report={"sheets": []}, clean=True)
        # Synthetic edit test only: real integration test keeps the actual editor/CLI guards.
        with (
            patch("pcbai.kicad.files.run", return_value=CompletedProcess([], 0, "", "")),
            patch("pcbai.tools.engine.rule_check", return_value=clean),
        ):
            edit = self.engine.call("set_value", dict(target, mode="preview", reference="R1", value="4k7"))
            applied = self.engine.call(
                "set_value", dict(target, mode="apply", candidate_id=edit["candidate_id"])
            )
        self.assertTrue(applied["ok"], applied)
        self.assertIn(b'"Value" "4k7"', sheet.read_bytes())
        status = self.engine.call(
            "update_marker_status",
            dict(
                applied["target"],
                mode="preview",
                n=1,
                status="done",
                reason="Value updated",
                evidence_id=applied["change_id"],
                markers_revision=saved["markers_revision"],
            ),
        )
        self.assertTrue(status["ok"], status)
        done = self.engine.call(
            "update_marker_status",
            dict(
                applied["target"],
                mode="apply",
                candidate_id=status["candidate_id"],
                markers_revision=status["markers_revision"],
            ),
        )
        self.assertTrue(done["ok"], done)
        marker = self.get()["markers"][0]
        self.assertEqual(marker["status"], "done")
        self.assertEqual(marker["evidence_id"], applied["change_id"])
        self.assertTrue(marker["trusted"])

    def test_orphaned_note_edit_preserves_anchor_and_missing_document_is_reported(self):
        self.apply(self.preview())
        self.board.write_bytes(GEOMETRY.replace(b'(uuid "front")', b'(uuid "removed")'))
        self.target = self.session.target(self.board.name)
        preview = self.preview(n=1)
        self.assertTrue(preview["ok"], preview)
        self.assertTrue(self.apply(preview)["ok"])
        self.assertEqual(self.get()["markers"][0]["binding"], "orphaned")
        self.board.unlink()
        self.assertEqual(self.get()["markers"][0]["binding"], "orphaned")

    def test_junction_escape_for_marker_folder_rejected(self):
        import os
        from pcbai.external import run

        if os.name != "nt":
            self.skipTest("Windows junction test")
        outside = self.root / "outside"
        outside.mkdir()
        response = run(["cmd", "/c", "mklink", "/J", str(self.file.parent), str(outside)], timeout=10)
        self.assertEqual(response.returncode, 0, response.stderr)
        # TemporaryDirectory cleans the junction itself, not the target directory.
        self.assertEqual(self.get()["error"]["code"], "outside_project")
        self.assertFalse(list(outside.iterdir()))
