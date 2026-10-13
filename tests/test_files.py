import os
import tempfile
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch

from pcbai.config import private_directory
from pcbai.core.contract import PcbAiError
from pcbai.external import run
from pcbai.history import History
from pcbai.kicad.files import assert_closed, atomic_write, revision, within, write_lock
from pcbai.permissions import descriptor_for, private_windows_acl, windows_owner
from subprocess import CompletedProcess
from tests.helpers import SCHEMATIC, make_project


class FileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = make_project(self.root / "project")

    def test_atomic_replace_failure_preserves_original_and_cleans_temp(self):
        path = self.project.with_suffix(".kicad_sch")
        with patch("pcbai.kicad.files.os.replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                atomic_write(path, b"different")
        self.assertEqual(path.read_bytes(), SCHEMATIC)
        self.assertEqual(list(path.parent.glob(".pcbai-*")), [])

    def test_cross_process_lock_is_exclusive_and_released(self):
        state = self.root / "lock-state"
        state.mkdir()
        before = set(self.project.parent.iterdir())
        with write_lock(self.project.parent, state):
            with self.assertRaises(PcbAiError), write_lock(self.project.parent / ".", state):
                pass
            if os.name == "nt":
                with self.assertRaises(PcbAiError), write_lock(str(self.project.parent).upper(), state):
                    pass
        with write_lock(self.project.parent, state):
            pass
        self.assertEqual(set(self.project.parent.iterdir()), before)
        self.assertEqual(len(list((state / "locks").glob("*.lock"))), 1)
        other = make_project(self.root / "other")
        with write_lock(self.project.parent, state), write_lock(other.parent, state):
            self.assertEqual(len(list((state / "locks").glob("*.lock"))), 2)

    def test_atomic_write_preserves_existing_permissions(self):
        path = self.project.with_suffix(".kicad_sch")
        if os.name == "nt":
            for protected in (False, True):
                with self.subTest(protected=protected):
                    if protected:
                        private_windows_acl([path], windows_owner(path))
                    before = descriptor_for(path, 5).raw
                    atomic_write(path, b"updated")
                    after = descriptor_for(path, 5).raw
                    # Windows can update SE_DACL_AUTO_INHERITED bookkeeping when restoring an ACL.
                    # Owner, ACEs, access masks and the inheritance-protection flag must stay identical.
                    self.assertEqual(after[4:], before[4:])
                    self.assertEqual(int.from_bytes(after[2:4], "little") & 0x1000,
                                     int.from_bytes(before[2:4], "little") & 0x1000)
        else:
            path.chmod(0o640)
            atomic_write(path, b"updated")
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)

    def test_nonempty_unknown_state_directory_rejected_without_changing_data(self):
        state = self.root / "unknown"
        state.mkdir()
        file = state / "user.txt"
        file.write_text("preserve me")
        with self.assertRaises(PcbAiError):
            private_directory(state)
        self.assertEqual(file.read_text(), "preserve me")

    @unittest.skipUnless(os.name == "nt", "Windows ACL regression")
    def test_existing_child_explicit_broad_acl_removed(self):
        state = private_directory(self.root / "private-old")
        nested = state / "nested"
        nested.mkdir()
        child = nested / "record.json"
        child.write_text("{}")
        output = run(["icacls", str(child), "/grant", "*S-1-1-0:F"])
        self.assertEqual(output.returncode, 0)
        broad = descriptor_for(child, 4).raw
        private_directory(state)
        secured = descriptor_for(child, 4).raw
        self.assertNotEqual(secured, broad)
        fresh = state / "fresh.json"
        fresh.write_text("{}")
        # Parent and descendants now have the same single-user effective ACL.
        self.assertNotIn("Everyone", run(["icacls", str(child)]).stdout)

    def test_project_manager_hosted_editors_block_writes(self):
        output = '"kicad.exe","123","Console","1","1 K"' if os.name == "nt" else "kicad\n"
        with patch("pcbai.kicad.files.run", return_value=CompletedProcess([], 0, output, "")):
            with self.assertRaises(PcbAiError) as caught:
                assert_closed(self.project.parent)
            self.assertEqual(caught.exception.code, "editor_open")

    def test_crashed_writer_does_not_leave_permanent_lock(self):
        import sys
        state = self.root / "lock-state"
        state.mkdir()
        env = dict(os.environ, PCBAI_TEST_ROOT=str(self.project.parent), PCBAI_TEST_STATE=str(state))
        script = ("import os,time; from pcbai.kicad.files import write_lock; "
                  "ctx=write_lock(os.environ['PCBAI_TEST_ROOT'],os.environ['PCBAI_TEST_STATE']); ctx.__enter__(); "
                  "print('locked', flush=True); time.sleep(30)")
        process = subprocess.Popen([sys.executable, "-c", script], env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            self.assertEqual(process.stdout.readline().strip(), b"locked")
            with self.assertRaises(PcbAiError), write_lock(self.project.parent, state):
                pass
        finally:
            process.terminate()
            process.communicate(timeout=10)
            process.stdout.close()
            process.stderr.close()
        with write_lock(self.project.parent, state):
            pass

    def test_project_rules_and_libraries_affect_revision(self):
        original = revision(self.project.parent)
        (self.project.parent / "Test.kicad_dru").write_text('(version 1)')
        self.assertNotEqual(revision(self.project.parent), original)
        after = revision(self.project.parent)
        (self.project.parent / "sym-lib-table").write_text('(sym_lib_table)')
        self.assertNotEqual(revision(self.project.parent), after)

    def test_checkpoint_integrity_and_wrong_target(self):
        state = self.root / "state"
        state.mkdir()
        history = History(state)
        cp = history.checkpoint("s1", "Test.kicad_sch", SCHEMATIC, "revision", "test")
        with self.assertRaises(PcbAiError):
            history.read(cp["id"], "s2", "Test.kicad_sch")
        (history.blobs / cp["sha256"]).write_bytes(b"corrupt")
        with self.assertRaises(PcbAiError):
            history.read(cp["id"], "s1", "Test.kicad_sch")
        with self.assertRaises(PcbAiError):
            history.read("cp-../../anything", "s1", "Test.kicad_sch")

    def test_symlink_escape_rejected(self):
        outside = self.root / "outside.kicad_sch"
        outside.write_bytes(SCHEMATIC)
        link = self.project.parent / "linked.kicad_sch"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("Symlink creation unavailable on this account")
        with self.assertRaises(PcbAiError):
            within(self.project.parent, link.name)

    def test_private_state_permissions(self):
        state = private_directory(self.root / "private")
        if os.name == "nt":
            output = run(["icacls", str(state)])
            self.assertEqual(output.returncode, 0)
            self.assertNotIn("(I)", output.stdout)
            self.assertNotIn("Everyone", output.stdout)
            self.assertNotIn("BUILTIN\\Users", output.stdout)
        else:
            self.assertEqual(state.stat().st_mode & 0o777, 0o700)

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_windows_junction_escape_rejected_without_touching_target(self):
        outside = self.root / "outside"
        outside.mkdir()
        marker = outside / "External.kicad_sch"
        marker.write_bytes(SCHEMATIC)
        link = self.project.parent / "linked"
        env = dict(os.environ, PCBAI_TEST_LINK=str(link), PCBAI_TEST_TARGET=str(outside))
        process = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "New-Item -ItemType Junction -Path $env:PCBAI_TEST_LINK "
                                  "-Target $env:PCBAI_TEST_TARGET | Out-Null"], env=env,
                                 capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
        try:
            with self.assertRaises(PcbAiError):
                within(self.project.parent, "linked/External.kicad_sch")
        finally:
            link.rmdir()  # Remove only the junction; the target file must survive.
        self.assertEqual(marker.read_bytes(), SCHEMATIC)
