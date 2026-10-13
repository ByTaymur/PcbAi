"""Private immutable checkpoints; no changes to the user's git history."""
import json
import uuid
from datetime import datetime, timezone

from pcbai.config import write_json
from pcbai.core.contract import PcbAiError
from pcbai.kicad.files import atomic_write, digest


class History:
    def __init__(self, state):
        self.root = state / "history"
        self.root.mkdir(exist_ok=True)
        self.blobs = self.root / "blobs"
        self.blobs.mkdir(exist_ok=True)

    def checkpoint(self, session, document, data, revision, label):
        sha = digest(data)
        blob = self.blobs / sha
        if not blob.exists():
            atomic_write(blob, data)
        entry = dict(id="cp-" + uuid.uuid4().hex, time=datetime.now(timezone.utc).isoformat(),
                     session=session, document=document, sha256=sha, revision=revision, label=label)
        write_json(self.root / (entry["id"] + ".json"), entry)
        return entry

    def read(self, checkpoint_id, session, document):
        if not isinstance(checkpoint_id, str) or not checkpoint_id.startswith("cp-"):
            raise PcbAiError("invalid_checkpoint", "Invalid checkpoint ID")
        suffix = checkpoint_id[3:]
        if len(suffix) != 32 or any(c not in "0123456789abcdef" for c in suffix):
            raise PcbAiError("invalid_checkpoint", "Invalid checkpoint ID")
        try:
            entry = json.loads((self.root / (checkpoint_id + ".json")).read_text(encoding="utf-8"))
            if entry["session"] != session or entry["document"] != document:
                raise PcbAiError("wrong_target", "Checkpoint belongs to a different target")
            sha = entry["sha256"]
            if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                raise ValueError("Invalid blob hash")
            data = (self.blobs / sha).read_bytes()
            if digest(data) != sha:
                raise ValueError("Checkpoint content hash mismatch")
            return data
        except (OSError, ValueError, KeyError) as exc:
            raise PcbAiError("invalid_checkpoint", "Checkpoint missing or corrupt") from exc

    def list(self, session):
        entries = [json.loads(path.read_text(encoding="utf-8")) for path in self.root.glob("cp-*.json")]
        return sorted((e for e in entries if e["session"] == session), key=lambda e: e["time"], reverse=True)
