"""KiCad → VS Code prompt handoff (plan AJ-5).

The KiCad window stores the prompt here and opens vscode://taymur.pcbai-vscode/handoff?id=<uuid>; the URL carries only
the id. The extension takes the prompt once, delivers it to its chosen agent and reports the outcome back, which the
KiCad window shows. Records live in <state>/handoff/<uuid>.json for 10 minutes and are single use.
"""
import json
import os
import re
import threading
import time
import uuid

from pcbai.core.contract import PcbAiError

LIFETIME = 600
PROMPT_LIMIT = 64000
OUTCOMES = {"sent", "typed", "typed+clipboard", "clipboard", "opened", "declined", "failed"}
_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


class Handoffs:
    def __init__(self, state, *, clock=time.time):
        self.folder = state / "handoff"
        self.clock = clock
        self.lock = threading.Lock()

    def _path(self, handoff_id):
        if not isinstance(handoff_id, str) or not _ID.match(handoff_id):
            raise PcbAiError("invalid_arguments", "Geçersiz devir kimliği")
        return self.folder / f"{handoff_id}.json"

    def _read(self, handoff_id):
        path = self._path(handoff_id)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise PcbAiError("not_found", "Devir bulunamadı ya da süresi geçti") from None
        if self.clock() - record["created"] > LIFETIME:
            path.unlink(missing_ok=True)
            raise PcbAiError("expired", "Devrin süresi geçti (10 dk); KiCad penceresinden yeniden gönderin")
        return path, record

    def _write(self, path, record):
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, path)

    def purge(self):
        for path in self.folder.glob("*.json") if self.folder.is_dir() else []:
            try:
                if self.clock() - json.loads(path.read_text(encoding="utf-8"))["created"] > LIFETIME:
                    path.unlink()
            except (OSError, ValueError, KeyError):
                path.unlink(missing_ok=True)

    def create(self, session, prompt):
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > PROMPT_LIMIT:
            raise PcbAiError("invalid_arguments", "İstem boş ya da çok uzun")
        with self.lock:
            self.folder.mkdir(parents=True, exist_ok=True)
            self.purge()
            handoff_id = str(uuid.uuid4())
            record = dict(id=handoff_id, created=self.clock(), session=session.id,
                          project=str(session.root / session.project), prompt=prompt, taken=False, outcome=None,
                          message=None)
            self._write(self._path(handoff_id), record)
            return handoff_id

    def take(self, handoff_id):
        """Single use: the prompt is returned once and removed from the record."""
        with self.lock:
            path, record = self._read(handoff_id)
            if record["taken"]:
                raise PcbAiError("already_taken", "Bu devir zaten kullanıldı")
            prompt = record["prompt"]
            record.update(taken=True, prompt=None)
            self._write(path, record)
            return dict(id=record["id"], session=record["session"], project=record["project"], prompt=prompt)

    def report(self, handoff_id, outcome, message=""):
        if outcome not in OUTCOMES:
            raise PcbAiError("invalid_arguments", "Bilinmeyen teslim sonucu")
        with self.lock:
            path, record = self._read(handoff_id)
            if not record["taken"]:
                raise PcbAiError("invalid_arguments", "Devir henüz alınmadı")
            record.update(outcome=outcome, message=str(message or "")[:300])
            self._write(path, record)
            return dict(ok=True)

    def status(self, handoff_id):
        with self.lock:
            _path, record = self._read(handoff_id)
            return dict(id=record["id"], taken=record["taken"], outcome=record["outcome"], message=record["message"])
