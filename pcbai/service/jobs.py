"""Bounded read-only jobs which outlive the submitting HTTP/MCP request."""
import copy
import secrets
import threading
import time
from datetime import datetime, timezone

from pcbai.core.contract import PcbAiError, error


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class Jobs:
    def __init__(self, *, limit=4, retained=100, full_results=20):
        self.limit = limit
        self.retained = retained
        self.full_results = full_results
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
                    self._trim_results()

            thread = threading.Thread(target=work, name=identity, daemon=True)
            self.threads[identity] = thread
            thread.start()
            return copy.deepcopy(entry)

    def _trim_results(self):
        """Keep full results of the newest ``full_results`` finished jobs; older ones keep ok/summary only (H7)."""
        finished = [e for e in self.entries.values() if e["status"] in {"completed", "failed"} and e["result"]]
        for entry in finished[:-self.full_results] if self.full_results else finished:
            result = entry["result"]
            if not result.get("result_trimmed"):
                entry["result"] = dict(ok=result.get("ok"), summary=result.get("summary"), result_trimmed=True,
                                       **({"error": result["error"]} if "error" in result else {}))

    def status(self, identity):
        with self.lock:
            if identity not in self.entries:
                raise PcbAiError("unknown_job", "Job is unknown, expired, or belongs to a previous service instance")
            return copy.deepcopy(self.entries[identity])

    def close(self, timeout=10.0):
        """Refuse new jobs and wait at most ``timeout`` seconds in total; returns the IDs still running.

        Job threads are daemons and engine children carry their own timeouts, so a stop never hangs on a long job.
        """
        with self.lock:
            self.closed = True
            threads = dict(self.threads)
        deadline = time.monotonic() + timeout
        for thread in threads.values():
            thread.join(max(0.0, deadline - time.monotonic()))
        return sorted(identity for identity, thread in threads.items() if thread.is_alive())
