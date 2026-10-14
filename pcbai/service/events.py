"""In-memory agent activity log (AJ-7). Records who called which tool and the outcome; never argument values.
The client name is data reported by the caller and grants nothing."""
import re
import threading
import time
from collections import deque

LIMIT = 500
FIXED_CLIENTS = {"vscode", "kicad", "builtin"}
BLOCKING_CODES = {"editor_open"}
_NAME = re.compile(r"[^a-z0-9._-]+")


def client_name(raw):
    """Normalize a reported client: fixed names stay, MCP clientInfo.name becomes mcp:<name>."""
    if not isinstance(raw, str) or not raw.strip():
        return "builtin"
    raw = raw.strip().lower()
    if raw in FIXED_CLIENTS:
        return raw
    if raw.startswith("mcp:"):
        raw = raw[4:]
    name = _NAME.sub("-", raw).strip("-")[:40]
    return "mcp:" + name if name else "mcp:unknown"


def outcome(output):
    if output.get("ok"):
        return "ok"
    code = (output.get("error") or {}).get("code") or "internal_error"
    return "blocked" if code in BLOCKING_CODES else "error:" + str(code)[:64]


def guidance(event, *, can_revert=False):
    """Turkish hint for the KiCad window, or None. can_revert comes from the AJ-S1 measurement."""
    if event.get("outcome") == "blocked":
        return ("Ajan değişiklik yapmak istiyor: kartı kaydedip PCB editörünü kapatın, sonra Devam deyin.")
    if event.get("outcome") == "ok" and event.get("change_id"):
        if can_revert:
            return "Ajan dosyayı değiştirdi: kartı yeniden yüklemek için Yeniden yükle'ye basın."
        return "Ajan dosyayı değiştirdi: KiCad'de Dosya → Geri al (Revert) ile kartı yeniden yükleyin."
    return None


class Events:
    def __init__(self, *, clock=time.time, limit=LIMIT):
        self.clock = clock
        self.items = deque(maxlen=limit)
        self.lock = threading.Lock()
        self.sequence = 0

    def record(self, client, tool, output):
        with self.lock:
            self.sequence += 1
            event = dict(seq=self.sequence, time=self.clock(), client=client_name(client), tool=tool,
                         outcome=outcome(output), change_id=output.get("change_id"))
            self.items.append(event)
            return dict(event)

    def recent(self, since=None, limit=50):
        """Events newer than `since` (a seq number), oldest first, at most `limit` (the newest ones)."""
        with self.lock:
            rows = [dict(e) for e in self.items if since is None or e["seq"] > since]
        return rows[-limit:] if limit else []
