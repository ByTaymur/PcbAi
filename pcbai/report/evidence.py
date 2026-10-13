import json
import uuid
import threading
from datetime import datetime, timezone

from pcbai.config import write_json
from pcbai.kicad.files import digest


class Evidence:
    def __init__(self, state):
        self.root = state / "evidence"
        self.root.mkdir(exist_ok=True)
        self.lock = threading.Lock()

    def record(self, *, tool, target, inputs, measurements, report):
        entry = dict(id="ev-" + uuid.uuid4().hex, time=datetime.now(timezone.utc).isoformat(),
                     tool=tool, target=target, inputs_hash=digest(json.dumps(inputs, sort_keys=True).encode()),
                     measurements=measurements, report_sha256=digest(json.dumps(report, sort_keys=True).encode()),
                     report=report)
        with self.lock:
            write_json(self.root / (entry["id"] + ".json"), entry)
        return entry
