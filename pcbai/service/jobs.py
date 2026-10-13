"""Bounded read-only jobs which outlive the submitting HTTP/MCP request."""
import copy
import secrets
import threading
from datetime import datetime, timezone

from pcbai.core.contract import PcbAiError, error


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class Jobs:
    def __init__(self, *, limit=4, retained=100):
        self.limit = limit
        self.retained = retained
        self.entries = {}
        self.threads = {}
        self.lock = threading.RLock()
        self.closed = False

    def submit(self, tool, arguments, operation):
        with self.lock:
            if self.closed:
                raise PcbAiError("service_stopping", "Job submission is closed")
            if len(self.threads) >= self.limit:
                raise PcbAiError("jobs_busy", "Too many active jobs; poll job_status before retrying")
            while len(self.entries) >= self.retained:
                oldest = next((k for k, v in self.entries.items() if v["status"] in {"completed", "failed"}), None)
                if oldest is None:
                    raise PcbAiError("jobs_busy", "Job history is full")
                del self.entries[oldest]
            identity = "job-" + secrets.token_hex(16)
            entry = dict(job_id=identity, tool=tool, target={k: arguments[k] for k in ("session", "document", "revision")},
                         status="queued", submitted_at=timestamp(), started_at=None, finished_at=None, result=None)
            self.entries[identity] = entry

            def work():
                with self.lock:
                    entry.update(status="running", started_at=timestamp())
                try:
                    output = operation()
                except Exception as exc:
                    output = error(PcbAiError("operation_failed", str(exc)))
                with self.lock:
                    entry.update(status="completed" if output.get("ok") else "failed",
                                 finished_at=timestamp(), result=output)
                    self.threads.pop(identity, None)

            thread = threading.Thread(target=work, name=identity, daemon=True)
            self.threads[identity] = thread
            thread.start()
            return copy.deepcopy(entry)

    def status(self, identity):
        with self.lock:
            if identity not in self.entries:
                raise PcbAiError("unknown_job", "Job is unknown, expired, or belongs to a previous service instance")
            return copy.deepcopy(self.entries[identity])

    def close(self):
        with self.lock:
            self.closed = True
            threads = list(self.threads.values())
        for thread in threads:
            thread.join()
