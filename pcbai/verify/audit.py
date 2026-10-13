"""Content-free, serialized and bounded audit metadata."""
import json
import threading
import time
from datetime import datetime, timezone

from pcbai.core.contract import PcbAiError
from pcbai.kicad.files import within, write_lock


def byte_count(value):
    try:
        return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError):
        return None


class AuditLog:
    def __init__(self, state, limit=10 * 1024 * 1024):
        self.state, self.limit, self.lock = state, limit, threading.Lock()

    def append(self, row):
        data = (json.dumps(dict(time=datetime.now(timezone.utc).isoformat(), **row),
                           ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self.lock:
            for attempt in range(50):
                try:
                    with write_lock(self.state / "audit-log", self.state):
                        path = within(self.state, "audit.jsonl", must_exist=False)
                        backup = within(self.state, "audit.1.jsonl", must_exist=False)
                        for target in (path, backup):
                            if target.exists() and target.stat().st_nlink > 1:
                                raise PcbAiError("unsafe_audit", "Audit hardlinks are not supported")
                        if path.exists() and path.stat().st_size + len(data) > self.limit:
                            backup.unlink(missing_ok=True)
                            path.replace(backup)
                        with path.open("ab") as stream:
                            stream.write(data)
                            stream.flush()
                    return
                except PcbAiError as exc:
                    if exc.code != "project_busy" or attempt == 49:
                        raise
                    time.sleep(.02)
