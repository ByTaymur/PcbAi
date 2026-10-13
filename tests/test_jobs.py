import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from pcbai.core.contract import PcbAiError
from pcbai.service.jobs import Jobs
from pcbai.tools.engine import Engine
from tests.helpers import make_project


TARGET = dict(session="s-test", document="Test.kicad_pcb", revision="sha256")


class JobTests(unittest.TestCase):
    def test_poll_capacity_failure_and_shutdown_drain(self):
        jobs = Jobs(limit=1)
        entered, release = threading.Event(), threading.Event()

        def work():
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test timed out")
            return dict(ok=False, error={"code": "timeout"})

        entry = jobs.submit("drc", TARGET, work)
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(2))
        status = jobs.status(entry["job_id"])
        self.assertEqual(status["status"], "running")
        status["target"]["revision"] = "tampered"
        self.assertEqual(jobs.status(entry["job_id"])["target"], TARGET)
        with self.assertRaises(PcbAiError) as caught:
            jobs.submit("drc", TARGET, work)
        self.assertEqual(caught.exception.code, "jobs_busy")
        closer = threading.Thread(target=jobs.close)
        closer.start()
        release.set()
        closer.join(3)
        self.assertFalse(closer.is_alive())
        status = jobs.status(entry["job_id"])
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["result"]["error"]["code"], "timeout")
        with self.assertRaises(PcbAiError):
            jobs.submit("drc", TARGET, work)

    def test_exception_and_history_are_bounded(self):
        jobs = Jobs(retained=1)

        def fail():
            raise RuntimeError("worker failed")

        first = jobs.submit("drc", TARGET, fail)
        with jobs.lock:
            threads = list(jobs.threads.values())
        for thread in threads:
            thread.join(2)
        self.assertEqual(jobs.status(first["job_id"])["result"]["error"]["code"], "operation_failed")
        second = jobs.submit("drc", TARGET, lambda: dict(ok=True))
        jobs.close()
        with self.assertRaises(PcbAiError):
            jobs.status(first["job_id"])
        self.assertEqual(jobs.status(second["job_id"])["status"], "completed")


class EngineJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        project = make_project(root / "project")
        (root / "state").mkdir()
        self.engine = Engine([project], root / "state")
        self.addCleanup(self.engine.jobs.close)
        self.session = next(iter(self.engine.sessions.entries.values()))
        self.target = self.session.target("Test.kicad_sch")

    def test_running_job_does_not_block_status_and_retains_error(self):
        entered, release = threading.Event(), threading.Event()

        def check(*_args, **_kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test timed out")
            raise PcbAiError("check_failed", "invalid schematic")

        with patch("pcbai.tools.engine.rule_check", check):
            submitted = self.engine.call("start_job", dict(self.target, tool="erc"))
            self.addCleanup(release.set)
            self.assertTrue(submitted["ok"], submitted)
            self.assertTrue(entered.wait(2))
            output = self.engine.call("job_status", {"job_id": submitted["job"]["job_id"]})
            self.assertEqual(output["job"]["status"], "running")
            release.set()
            self.engine.jobs.close()
        status = self.engine.call("job_status", {"job_id": submitted["job"]["job_id"]})["job"]
        self.assertEqual(status["result"]["error"]["code"], "check_failed")
        self.assertEqual(status["target"], self.target)

    def test_invalid_or_write_job_and_stale_submission_rejected(self):
        for args in [dict(self.target, tool="set_value"), dict(self.target, tool="erc", width=80),
                     dict(self.target, tool="erc", revision="old"),
                     dict(self.target, tool="render_board")]:
            output = self.engine.call("start_job", args)
            self.assertFalse(output["ok"], output)
        self.assertEqual(self.engine.jobs.entries, {})

    def test_change_between_submit_and_execution_fails_without_check(self):
        with self.session.lock, patch("pcbai.tools.engine.rule_check") as check:
            submitted = self.engine.call("start_job", dict(self.target, tool="erc"))
            self.assertTrue(submitted["ok"], submitted)
            path = self.session.root / self.target["document"]
            path.write_bytes(path.read_bytes() + b"\n")
        self.engine.jobs.close()
        output = self.engine.jobs.status(submitted["job"]["job_id"])
        self.assertEqual(output["result"]["error"]["code"], "stale_revision")
        check.assert_not_called()
