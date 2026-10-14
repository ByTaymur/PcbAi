import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from pcbai.core.contract import PcbAiError
from pcbai.external import run
from pcbai.kicad.cli import snapshot
from pcbai.kicad.files import digest, revision
from pcbai.tools.engine import Engine
from pcbai.verify.findings import normalize_findings
from pcbai.verify.waivers import FILE, MAX_BYTES, decode, disposition, max_days, read
from tests.helpers import make_project
from tests.test_kicad_integration import demo_root

DAY = date(2026, 10, 14)


def finding(uid="a", severity="error"):
    return dict(type="pin_not_connected", severity=severity, items=[dict(uuid=uid, pos=dict(x=1, y=2))])


def record(identity, **extra):
    return dict(dict(finding_id=identity, reason="Accepted test finding; text is data $(never execute)",
                     owner="fixture owner", created="2026-10-14", expires="2026-10-15"), **extra)


def encode(records):
    return json.dumps(dict(version=1, waivers=records)).encode()


class WaiverDataTests(unittest.TestCase):
    def setUp(self):
        self.rows = normalize_findings([finding()], "erc")
        self.entry = record(self.rows[0]["finding_id"])

    def test_exact_expiry_boundary_and_data_unchanged(self):
        payload = decode(encode([self.entry]), DAY, 90)
        before = json.dumps(self.rows, sort_keys=True)
        output = disposition(self.rows, payload, DAY)
        self.assertEqual(output["active_findings"], [])
        self.assertEqual(len(output["waived"]), 1)
        self.assertEqual(output["next_waiver_expiry"], "2026-10-15")
        self.assertEqual(json.dumps(self.rows, sort_keys=True), before)
        expired = disposition(self.rows, payload, DAY + timedelta(days=1))
        self.assertEqual(expired["active_findings"], self.rows)
        self.assertFalse(expired["waived"])
        self.assertTrue(expired["waiver_warnings"][0].startswith("waiver_expired:"))

    def test_orphan_and_identity_change_do_not_waive_other_findings(self):
        payload = decode(encode([self.entry]), DAY, 90)
        rows = normalize_findings([finding("different")], "erc")
        output = disposition(rows, payload, DAY)
        self.assertEqual(output["active_findings"], rows)
        self.assertEqual(output["orphaned_waivers"], [self.entry])

    def test_duplicate_ordinal_is_exact_not_base_match(self):
        rows = normalize_findings([finding(), finding()], "erc")
        output = disposition(rows, decode(encode([record(rows[0]["finding_id"])]), DAY, 90), DAY)
        self.assertEqual(len(output["waived"]), 1)
        self.assertEqual(output["active_findings"], [rows[1]])
        base = disposition(rows, decode(encode([self.entry]), DAY, 90), DAY)
        self.assertFalse(base["waived"])

    def test_identity_deliberately_survives_uuid_motion_and_severity_change(self):
        row = finding(severity="warning")
        row["items"][0]["pos"] = dict(x=500, y=600)
        moved = normalize_findings([row], "erc")
        self.assertEqual(moved[0]["finding_id"], self.entry["finding_id"])
        self.assertEqual(len(disposition(moved, decode(encode([self.entry]), DAY, 90), DAY)["waived"]), 1)

    def test_invalid_record_fields_dates_and_prefixes(self):
        bad = [dict(reason=" "), dict(owner=""), dict(created="2026-10-16"), dict(expires="2026-10-14"),
               dict(expires="2027-10-15"), dict(expires="20261015"), dict(expires="2026-02-30"),
               dict(finding_id="erc:*:aaaaaaaaaaaa"), dict(finding_id="readback:test:aaaaaaaaaaaa"),
               dict(extra="unknown"), dict(created=True)]
        for extra in bad:
            with self.subTest(extra=extra), self.assertRaises(PcbAiError):
                decode(encode([dict(self.entry, **extra)]), DAY, 90)
        incomplete = dict(self.entry)
        incomplete.pop("expires")
        with self.assertRaises(PcbAiError):
            decode(encode([incomplete]), DAY, 90)

    def test_malformed_envelope_duplicate_keys_nan_size_and_duplicates(self):
        bad = [b"", b"[]", b'{"version":1,"version":1,"waivers":[]}',
               b'{"version":NaN,"waivers":[]}', b'{"version":true,"waivers":[]}',
               b'{"version":1,"waivers":{},"extra":1}', b" " * (MAX_BYTES + 1),
               encode([self.entry, self.entry]), encode([True]), encode([self.entry] * 1001)]
        for raw in bad:
            with self.subTest(raw=raw[:80]), self.assertRaises(PcbAiError):
                decode(raw, DAY, 90)

    def test_environment_policy_bounds(self):
        for value in ("0", "-1", "true", "366", "1.5", "", " 90", "090"):
            with self.subTest(value=value), patch.dict(os.environ, PCBAI_WAIVER_MAX_DAYS=value):
                with self.assertRaises(PcbAiError):
                    max_days()
        with patch.dict(os.environ, PCBAI_WAIVER_MAX_DAYS="30"):
            self.assertEqual(max_days(), 30)
            # H3: a record longer than the lowered policy no longer locks the file; it is visible and waives nothing.
            payload = decode(encode([record(self.entry["finding_id"], expires="2026-12-01")]), DAY, max_days())
            output = disposition(self.rows, payload, DAY, max_days())
            self.assertEqual(output["active_findings"], self.rows)
            self.assertEqual([r["finding_id"] for r in output["policy_exceeded_waivers"]], [self.entry["finding_id"]])
            self.assertTrue(output["waiver_warnings"][-1].startswith("waiver_policy_exceeded:"))


class WaiverEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.project = make_project(root / "project")
        state = root / "state"
        state.mkdir()
        self.engine = Engine([self.project], state)
        self.addCleanup(self.engine.jobs.close)
        self.session = next(iter(self.engine.sessions.entries.values()))
        self.path = self.project.parent / FILE
        self.rows = normalize_findings([finding()], "erc")
        self.entry = record(self.rows[0]["finding_id"])
        self.addCleanup(patch.stopall)
        patch("pcbai.verify.waivers.today", return_value=DAY).start()
        patch.dict(os.environ, PCBAI_WAIVER_MAX_DAYS="90").start()
        patch.object(self.engine, "_check_tool_version", return_value="fixture").start()

    def check(self, *, extra=None, during=None):
        original = self.engine._call
        def call(name, args, session):
            if name == "check":
                return original(name, args, session)
            if during:
                during()
            return dict(ok=True, findings=self.rows, checks_run=extra or [])
        with patch.object(self.engine, "_call", side_effect=call):
            return self.engine.call("check", dict(session=self.session.id, scope="sch"))

    def preview(self, *, delete=False):
        current = self.engine.call("get_waivers", dict(session=self.session.id))
        args = dict(self.session.target(self.project.name), mode="preview", waivers_revision=current["waivers_revision"])
        args.update(dict(finding_id=self.entry["finding_id"]) if delete else dict(waiver=self.entry))
        return args, self.engine.call("delete_waiver" if delete else "set_waiver", args)

    def apply(self, args, preview, *, delete=False, **extra):
        apply_args = {k: v for k, v in args.items() if k not in {"waiver", "finding_id"}}
        apply_args.update(mode="apply", candidate_id=preview["candidate_id"], **extra)
        with patch("pcbai.verify.waivers.assert_closed"):
            return self.engine.call("delete_waiver" if delete else "set_waiver", apply_args)

    def test_all_waived_report_preserves_findings_child_results_and_evidence(self):
        self.path.write_bytes(encode([self.entry]))
        output = self.check()
        self.assertEqual(output["verified"], "checks_ok", output)
        self.assertEqual(output["findings"], self.rows)
        self.assertEqual(output["results"]["erc"]["findings"], self.rows)
        self.assertEqual(output["waived"][0]["waiver"], self.entry)
        self.assertIn("1 waived, next expiry 2026-10-15", output["summary"])
        evidence = json.loads((self.engine.evidence.root / (output["evidence_id"] + ".json")).read_text())
        self.assertEqual(evidence["report"]["findings"], self.rows)
        self.assertEqual(evidence["report"]["waiver_policy"]["sha256"], digest(self.path.read_bytes()))

    def test_ignored_required_coverage_cannot_be_waived(self):
        self.path.write_bytes(encode([self.entry]))
        from pcbai.verify.manifest import entry
        output = self.check(extra=[entry("erc_rule:pin_not_connected", status="skipped", reason="rule_ignored_in_project")])
        self.assertEqual(output["verified"], "checks_incomplete")
        self.assertEqual(len(output["waived"]), 1)

    def test_invalid_file_runs_checks_but_is_incomplete(self):
        self.path.write_bytes(b"{}")
        output = self.check()
        self.assertEqual(output["verified"], "checks_incomplete", output)
        self.assertEqual(output["checks_run"][0]["reason"], "invalid_waivers")
        self.assertEqual(output["findings"], self.rows)

    def test_expired_and_orphan_are_visible(self):
        self.path.write_bytes(encode([dict(self.entry, created="2026-10-12", expires="2026-10-14"),
                                     record("drc:clearance:aaaaaaaaaaaa")]))
        output = self.check()
        self.assertEqual(output["verified"], "checks_findings")
        self.assertEqual(len(output["expired_waivers"]), 1)
        self.assertEqual(len(output["orphaned_waivers"]), 1)

    def test_fixture24_expired_waiver_is_active(self):
        source = Path(__file__).parent / "fixtures/faults/24-expired-waiver" / FILE
        self.path.write_bytes(source.read_bytes())
        output = self.check()
        self.assertEqual(output["verified"], "checks_findings")
        self.assertEqual(output["active_findings"], self.rows)
        self.assertFalse(output["waived"])
        self.assertTrue(any(w.startswith("waiver_expired:") for w in output["warnings"]))

    def test_policy_is_revision_and_snapshot_input(self):
        before = revision(self.project.parent)
        self.path.write_bytes(encode([self.entry]))
        self.assertNotEqual(before, revision(self.project.parent))
        with snapshot(self.project.parent, revision(self.project.parent)) as root:
            self.assertEqual((root / FILE).read_bytes(), self.path.read_bytes())

    def test_policy_changed_during_check_is_incomplete(self):
        output = self.check(during=lambda: self.path.write_bytes(encode([self.entry])))
        self.assertEqual(output["verified"], "checks_incomplete")
        self.assertFalse(output["waived"])

    def test_preview_apply_checkpoint_and_delete(self):
        args, preview = self.preview()
        self.assertTrue(preview["ok"], preview)
        self.assertFalse(self.path.exists())
        output = self.apply(args, preview)
        self.assertTrue(output["changed"], output)
        self.assertEqual(self.engine.history.read(output["checkpoint"]["id"], self.session.id, FILE), b"")
        self.assertEqual(output["waivers_revision"], preview["after_sha256"])
        old = self.path.read_bytes()
        args, preview = self.preview(delete=True)
        output = self.apply(args, preview, delete=True)
        self.assertTrue(output["ok"], output)
        self.assertEqual(read(self.project.parent, DAY, 90)[0]["waivers"], [])
        self.assertEqual(self.engine.history.read(output["checkpoint"]["id"], self.session.id, FILE), old)

    def test_apply_rejects_changed_revision_new_parameters_wrong_tool_or_target(self):
        args, preview = self.preview()
        self.assertEqual(self.apply(args, preview, waiver=self.entry)["error"]["code"], "invalid_arguments")
        self.assertEqual(self.apply(args, preview, delete=True)["error"]["code"], "wrong_target")
        wrong = dict(args, document="Test.kicad_sch")
        self.assertEqual(self.apply(wrong, preview)["error"]["code"], "wrong_target")
        self.path.write_bytes(encode([]))
        self.assertEqual(self.apply(args, preview)["error"]["code"], "stale_revision")

    def test_corrupt_file_is_restored_from_checkpoint(self):
        args, preview = self.preview()
        saved = self.apply(args, preview)
        good = self.path.read_bytes()
        args, preview = self.preview(delete=True)
        deleted = self.apply(args, preview, delete=True)
        self.path.write_bytes(b"{corrupt")
        current = self.engine.call("get_waivers", dict(session=self.session.id))
        self.assertEqual(current["error"]["code"], "invalid_waivers")
        base = dict(self.session.target(self.project.name), waivers_revision=current["waivers_revision"])
        for checkpoint, expected in [(deleted["checkpoint"]["id"], good), (saved["checkpoint"]["id"], None)]:
            with self.subTest(checkpoint=checkpoint):
                restore = self.engine.call("restore_waivers", dict(base, mode="preview", checkpoint_id=checkpoint))
                self.assertTrue(restore["ok"], restore)
                apply_args = dict(base, mode="apply", candidate_id=restore["candidate_id"])
                with patch("pcbai.verify.waivers.assert_closed"):
                    output = self.engine.call("restore_waivers", apply_args)
                self.assertTrue(output["ok"], output)
                if expected is None:
                    self.assertFalse(self.path.exists())
                else:
                    self.assertEqual(self.path.read_bytes(), expected)
                base = dict(output["target"], waivers_revision=output["waivers_revision"])
        bogus = self.engine.call("restore_waivers", dict(base, mode="preview", checkpoint_id="cp-" + "0" * 32))
        self.assertEqual(bogus["error"]["code"], "invalid_checkpoint")

    def test_policy_exceeded_record_can_be_deleted(self):
        long = dict(self.entry, created=date.today().isoformat(),
                    expires=(date.today() + timedelta(days=60)).isoformat())
        self.path.write_bytes(encode([long]))
        with patch.dict(os.environ, PCBAI_WAIVER_MAX_DAYS="30"):
            current = self.engine.call("get_waivers", dict(session=self.session.id))
            self.assertTrue(current["ok"], current)
            self.assertEqual(current["policy_exceeded"], [self.entry["finding_id"]])
            args, preview = self.preview(delete=True)
            self.assertTrue(preview["ok"], preview)
            output = self.apply(args, preview, delete=True)
        self.assertTrue(output["ok"], output)
        self.assertEqual(json.loads(self.path.read_bytes())["waivers"], [])

    def test_apply_rechecks_expiry_and_policy(self):
        args, preview = self.preview()
        with patch("pcbai.verify.waivers.today", return_value=DAY + timedelta(days=1)):
            output = self.apply(args, preview)
        self.assertEqual(output["error"]["code"], "invalid_waivers")
        self.assertFalse(self.path.exists())
        with patch.dict(os.environ, PCBAI_WAIVER_MAX_DAYS="30"):
            output = self.apply(args, preview)
        self.assertEqual(output["error"]["code"], "stale_waivers")

    def test_corrupt_file_cannot_be_overwritten_and_editor_lock_blocks_apply(self):
        self.path.write_bytes(b"{}")
        output = self.engine.call("get_waivers", dict(session=self.session.id))
        self.assertEqual(output["error"]["code"], "invalid_waivers")
        self.path.unlink()
        args, preview = self.preview()
        with patch("pcbai.verify.waivers.assert_closed", side_effect=PcbAiError("editor_open", "fixture")):
            apply_args = {k: v for k, v in args.items() if k != "waiver"}
            apply_args.update(mode="apply", candidate_id=preview["candidate_id"])
            output = self.engine.call("set_waiver", apply_args)
        self.assertEqual(output["error"]["code"], "editor_open")
        self.assertFalse(self.path.exists())

    def test_direct_erc_remains_unwaived(self):
        self.path.write_bytes(encode([self.entry]))
        check = dict(errors=1, warning_count=0, clean=False, findings=[finding()], report=dict(native="untouched"))
        with patch("pcbai.tools.engine.rule_check", return_value=check):
            output = self.engine.call("erc", self.session.target("Test.kicad_sch"))
        self.assertEqual(output["verified"], "erc_findings")
        self.assertNotIn("waived", output)

    def test_partial_waiver_and_missing_required_tool_keep_gate_closed(self):
        self.rows = normalize_findings([finding(), finding("b")], "erc")
        self.path.write_bytes(encode([self.entry]))
        output = self.check()
        self.assertEqual(output["verified"], "checks_findings")
        self.assertEqual(len(output["active_findings"]), 1)
        with patch.dict(os.environ, PCBAI_KICAD_CLI=str(self.project.parent / "absent-cli")):
            output = self.engine.call("check", dict(session=self.session.id, scope="sch"))
        self.assertEqual(output["verified"], "checks_incomplete")

    def test_saved_readback_mismatch_and_evidence_failure_preserve_changed(self):
        args, preview = self.preview()
        from pcbai.kicad.files import atomic_write
        def wrong(path, data):
            atomic_write(path, encode([]))
        with patch("pcbai.verify.waivers.atomic_write", side_effect=wrong):
            output = self.apply(args, preview)
        self.assertFalse(output["ok"], output)
        self.assertTrue(output["changed"])
        self.assertEqual(output["verified"], "readback_mismatch")
        self.assertIn("checkpoint", output)
        args, preview = self.preview()
        with patch.object(self.engine.evidence, "record", side_effect=OSError("fixture")):
            output = self.apply(args, preview)
        self.assertTrue(output["changed"], output)
        self.assertEqual(output["verified"], "saved_sha256_ok")
        self.assertTrue(output["warnings"][0].startswith("evidence_write_failed:"))

    def test_external_sidecar_symlink_is_rejected(self):
        external = Path(self.temp.name) / "outside.json"
        external.write_bytes(encode([self.entry]))
        try:
            self.path.symlink_to(external)
        except OSError:
            self.skipTest("OS does not permit unprivileged symlinks")
        with self.assertRaises(PcbAiError) as caught:
            read(self.project.parent, DAY, 90)
        self.assertEqual(caught.exception.code, "outside_project")

    def test_directory_and_oversized_policy_cannot_disappear_from_snapshot(self):
        self.rows = []
        self.path.mkdir()
        output = self.check()
        self.assertEqual(output["verified"], "checks_incomplete", output)
        self.assertEqual(output["error"]["code"], "invalid_waivers")
        self.path.rmdir()
        self.path.write_bytes(b" " * (MAX_BYTES + 1))
        output = self.check()
        self.assertEqual(output["verified"], "checks_incomplete", output)
        self.assertEqual(output["error"]["code"], "invalid_waivers")
        with self.assertRaises(PcbAiError):
            with snapshot(self.project.parent):
                self.fail("Oversized policy must not be copied")

    def test_distinct_sessions_share_atomic_global_preview_limit(self):
        from pcbai.service.sessions import Sessions
        second_project = make_project(Path(self.temp.name) / "second-project")
        second = next(iter(Sessions([second_project]).entries.values()))
        self.engine.sessions.entries[second.id] = second
        def args(session):
            return dict(session.target(session.project), mode="preview", waivers_revision=digest(b""), waiver=self.entry)
        for _ in range(99):
            self.assertTrue(self.engine.call("set_waiver", args(self.session))["ok"])
        start = threading.Barrier(2)
        import secrets
        token = secrets.token_hex
        def slow_token(size):
            # Widen the interval between limit check and insertion across distinct session locks.
            time.sleep(0.1)
            return token(size)
        def preview(session):
            start.wait(timeout=5)
            return self.engine.call("set_waiver", args(session))
        with patch("pcbai.verify.waivers.secrets.token_hex", side_effect=slow_token), ThreadPoolExecutor(2) as pool:
            first = pool.submit(preview, self.session)
            last = pool.submit(preview, second)
            outputs = [first.result(timeout=10), last.result(timeout=10)]
        self.assertEqual(sum(output["ok"] for output in outputs), 1, outputs)
        self.assertEqual(len(self.engine.waivers.previews), 100)
        for output in outputs:
            if output["ok"]:
                self.assertIn(output["candidate_id"], self.engine.waivers.previews)
            else:
                self.assertEqual(output["error"]["code"], "too_many_candidates")


class WaiverRealCLITests(unittest.TestCase):
    def test_real_parity_waiver_exit0_expired_exit1_bad_policy_exit2(self):
        if demo_root() is None:
            self.skipTest("Real KiCad CLI required")
        source = Path(__file__).parent / "fixtures/faults/01-drc-zero-short"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(source, root / "project")
            project = root / "project/fault.kicad_pro"
            state = root / "engine-state"
            state.mkdir()
            engine = Engine([project], state)
            self.addCleanup(engine.jobs.close)
            session = next(iter(engine.sessions.entries.values()))
            output = engine.call("check", dict(session=session.id, scope="pcb"))
            self.assertEqual(output["verified"], "checks_findings", output)
            now = datetime.now(timezone.utc).date()
            records = [record(row["finding_id"], created=now.isoformat(),
                              expires=(now + timedelta(days=1)).isoformat()) for row in output["findings"]]
            path = project.parent / FILE
            env = dict(os.environ, PCBAI_STATE_DIR=str(root / "cli-state"), PCBAI_WAIVER_MAX_DAYS="90")
            for raw, code in ((encode(records), 0),
                              (encode([dict(r, created=(now - timedelta(days=1)).isoformat(),
                                            expires=now.isoformat()) for r in records]), 1), (b"{}", 2)):
                path.write_bytes(raw)
                native_before = {p.name: p.read_bytes() for p in project.parent.glob("*.kicad_*")}
                result = run([sys.executable, "-m", "pcbai", "check", project, "--scope", "pcb", "--json"],
                             env=env, timeout=240)
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(len(report["findings"]), len(records))
                self.assertEqual({p.name: p.read_bytes() for p in project.parent.glob("*.kicad_*")}, native_before)
                if code == 0:
                    self.assertEqual(len(report["waived"]), len(records))
                if code == 1:
                    self.assertTrue(report["expired_waivers"])
