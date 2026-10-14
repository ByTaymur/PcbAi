"""PcbAi Asistan window logic without wx (plan AJ-4): agent catalogue, detection, KiCad selection rows, prompt,
delivery and the single-instance lock. assistant_window.py draws it; tests drive this module directly.

Every external program runs with an argument list (shell=False) and a timeout; only .exe files are started.
The prompt text comes from the service (POST /agent/prompt, AJ-3) so the window, the VS Code panel and the
board/schematic views send the same words.
"""
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import quote

CLI_MAX = 7000
DETECT_TIMEOUT = 3
PROMPT_LIFETIME = 24 * 3600
VSCODE_EXTENSION = "taymur.pcbai-vscode"
CLAUDE_EXTENSION = "anthropic.claude-code"

# Rows of the KiCad window (plan AJ-4 table). "available" is filled by detect().
CATALOG = [
    dict(id="vscode", label="VS Code'daki ajan — VS Code panelinde seçili ajana gider", kind="handoff"),
    dict(id="claude-cli", label="Claude Code (terminal) — doğrudan gönderilir", kind="cli", program="claude"),
    dict(id="codex-cli", label="Codex (terminal) — doğrudan gönderilir", kind="cli", program="codex"),
    dict(id="builtin", label="Yerleşik model — bu pencerede", kind="builtin"),
    dict(id="clipboard", label="Sadece panoya kopyala — istediğin yere yapıştır", kind="clipboard"),
]


def _env_path(name, default=None):
    value = os.environ.get(name)
    return Path(value) if value else default


def known_paths(program):
    """Install locations used when the program is not on PATH (KiCad's environment is often minimal)."""
    home = Path.home()
    local = _env_path("LOCALAPPDATA", home / "AppData" / "Local")
    if program == "claude":
        return [home / ".local" / "bin" / "claude.exe"]
    if program == "codex":
        return sorted((local / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"), reverse=True)
    if program == "code":
        return [local / "Programs" / "Microsoft VS Code" / "Code.exe"]
    return []


def find_program(program, which=shutil.which, exists=Path.is_file):
    """Absolute path of program.exe, or None. A .cmd/.ps1 shim is refused: it would need a shell."""
    found = which(program + ".exe") or which(program)
    candidates = ([Path(found)] if found else []) + known_paths(program)
    for candidate in candidates:
        if candidate.suffix.lower() == ".exe" and exists(candidate):
            return candidate
    return None


def vscode_extensions(path=None):
    """Installed VS Code extension ids (lower case) from extensions.json; empty when unreadable."""
    path = path or Path.home() / ".vscode" / "extensions" / "extensions.json"
    try:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
        return {r["identifier"]["id"].lower() for r in rows if isinstance(r, dict) and "identifier" in r}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return set()


def detect(find=find_program, extensions=vscode_extensions):
    """Catalogue rows with availability. Runs once when the window opens."""
    started = time.monotonic()
    installed = extensions()
    rows = []
    for entry in CATALOG:
        row = dict(entry, available=False, path=None, reason="")
        if time.monotonic() - started > DETECT_TIMEOUT and entry["kind"] == "cli":
            row["reason"] = "algılama zaman aşımı"
        elif entry["kind"] == "cli":
            path = find(entry["program"])
            row.update(available=path is not None, path=path, reason="" if path else "kurulu değil")
        elif entry["kind"] == "handoff":
            ok = VSCODE_EXTENSION in installed
            row.update(available=ok, reason="" if ok else "PcbAi VS Code eklentisi kurulu değil")
            row["claude_fallback"] = not ok and CLAUDE_EXTENSION in installed
        else:
            row["available"] = True  # builtin: provider readiness is shown in its own row of the window
        rows.append(row)
    return rows


def default_row(rows, saved=None):
    for row in rows:
        if row["id"] == saved and row["available"]:
            return row
    return next(r for r in rows if r["available"])


# --- KiCad selection -------------------------------------------------------------------------------------------

def _get(obj, *names):
    for name in names:
        if obj is None:
            return None
        obj = getattr(obj, name, None)
        if callable(obj):
            try:
                obj = obj()
            except TypeError:
                return None
    return obj


def _mm(value):
    return round(value / 1e6, 4) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _layer(item):
    layer = _get(item, "layer")
    if layer is None:
        return None
    try:
        from kipy.util.board_layer import canonical_name
        return canonical_name(layer)
    except Exception:  # kipy missing or unknown layer: the enum number is still data
        return str(layer)


def selection_rows(items):
    """kipy selection objects → plain rows for the prompt (type, reference, value, net, layer, x_mm, y_mm)."""
    rows = []
    for item in items:
        kind = type(item).__name__
        position = _get(item, "position") or _get(item, "start")
        row = dict(type={"FootprintInstance": "footprint", "Track": "track", "ArcTrack": "arc", "Via": "via",
                         "Pad": "pad", "Zone": "zone"}.get(kind, kind),
                   reference=_get(item, "reference_field", "text", "value") or _get(item, "number"),
                   value=_get(item, "value_field", "text", "value"),
                   net=_get(item, "net", "name"), layer=_layer(item),
                   x_mm=_mm(_get(position, "x")), y_mm=_mm(_get(position, "y")),
                   uuid=_get(item, "id", "value"))
        rows.append({k: v for k, v in row.items() if v not in (None, "")})
    return rows


def selection_summary(rows):
    names = [r.get("reference") or (r.get("net") and "net " + r["net"]) or r["type"] for r in rows[:3]]
    more = f" +{len(rows) - 3}" if len(rows) > 3 else ""
    return f"{len(rows)} öğe: {', '.join(names)}{more}" if rows else "seçim yok"


# --- Markers (plan IM) -----------------------------------------------------------------------------------------

def pcb_marker(rows, note):
    """KiCad PCB selection → marker. A footprint with a UUID anchors it; otherwise the first located item is a point."""
    located = [r for r in rows if r.get("x_mm") is not None and r.get("y_mm") is not None]
    if not located:
        return None
    row = next((r for r in located if r["type"] == "footprint" and r.get("uuid")), located[0])
    marker = dict(kind="point", space="pcb", points_mm=[[row["x_mm"], row["y_mm"]]], note=note)
    if row.get("layer"):
        marker["layer"] = row["layer"]
    if row["type"] == "footprint" and row.get("uuid"):
        marker.update(kind="item", anchor=dict(type="footprint", uuid=row["uuid"]))
    return marker


def root_sheet(schematic):
    """Root sheet instance path ("/<uuid>") from the saved root schematic's first uuid."""
    match = re.search(rb'\(uuid\s+"?([0-9a-fA-F-]{36})"?\)', Path(schematic).read_bytes())
    if not match:
        raise RuntimeError(f"Şematik kimliği bulunamadı: {Path(schematic).name}")
    return "/" + match.group(1).decode().lower()


def sch_symbols(scene):
    """Placed, non-power symbols of one page instance, sorted by reference."""
    rows = [i for i in scene.get("items", []) if i.get("type") == "symbol" and not i.get("power") and i.get("uuid")]
    return sorted(rows, key=lambda r: (re.sub(r"\d+", "", r.get("reference", "")),
                                       int((re.findall(r"\d+", r.get("reference", "")) or ["0"])[0])))


def sch_marker(symbol, sheet, note):
    return dict(kind="item", space="sch", points_mm=[list(symbol["at"])], note=note, sheet=sheet,
                anchor=dict(type="symbol", uuid=symbol["uuid"]))


def _view(client, name, arguments):
    response = client.request("POST", "/view/call", {"name": name, "arguments": arguments})
    if not response.get("ok"):
        error = response.get("error") or {}
        raise MarkerError(error.get("code", ""), error.get("message") or response.get("summary") or "İşaret kaydedilemedi")
    return response


class MarkerError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def save_marker(client, session_id, document, marker=None, n=None, note=None, delete=False):
    """Preview then apply one marker edit through the view endpoint (same path as the VS Code panel).

    New marker: ``marker``. Note change: ``n`` + ``note`` (the stored geometry is kept). Delete: ``n`` + delete.
    Returns the saved marker (None after delete).
    """
    state = client.request("POST", "/call", {"name": "get_markers", "arguments": {"session": session_id}})
    if not state.get("ok"):
        raise RuntimeError(state.get("summary") or "İşaretler okunamadı")
    if n is not None and not delete:
        stored = next((m for m in state.get("markers", []) if m["n"] == n), None)
        if stored is None:
            raise RuntimeError(f"#{n} işareti yok")
        marker = {k: stored[k] for k in ("kind", "space", "points_mm", "layer", "sheet", "anchor") if k in stored}
        marker["note"] = note
        document = stored["document"]
    target = dict(session=session_id, document=document, revision=state["revision"])
    args = dict(target, markers_revision=state["markers_revision"], mode="preview")
    if n is not None:
        args["n"] = n
    if not delete:
        args["marker"] = marker
    tool = "delete_marker" if delete else "set_marker"
    preview = _view(client, tool, args)
    _view(client, tool, dict(target, markers_revision=preview["markers_revision"], mode="apply",
                             candidate_id=preview["candidate_id"]))
    return preview.get("marker")


# --- Prompt and delivery ---------------------------------------------------------------------------------------

def compose(client, session_id, request, marker_ids, selection):
    response = client.request("POST", "/agent/prompt", {"session": session_id, "request": request,
                                                         "marker_ids": marker_ids, "selection": selection or None})
    if not response.get("ok"):
        raise RuntimeError((response.get("error") or {}).get("message") or "İstem oluşturulamadı")
    return response["prompt"]


def cli_safe(prompt):
    """One line for a command-line argument: line breaks become spaces, quotes stay (argv list, no shell)."""
    return " ".join(prompt.split())


def prompt_file(project_root, prompt, now=time.time):
    """Long prompt → <project>/.pcbai-state/prompts/<uuid>.md; files older than 24 h are removed first."""
    folder = Path(project_root) / ".pcbai-state" / "prompts"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.md"):
        try:
            if now() - old.stat().st_mtime > PROMPT_LIFETIME:
                old.unlink()
        except OSError:
            pass
    path = folder / f"{uuid.uuid4()}.md"
    path.write_text(prompt, encoding="utf-8")
    return path


def cli_argument(prompt, project_root):
    text = cli_safe(prompt)
    if len(text) <= CLI_MAX:
        return text
    path = prompt_file(project_root, prompt)
    return f"PcbAi isteği uzun; {path} dosyasındaki isteği oku ve uygula."


def deliver(row, prompt, project_root, *, popen=subprocess.Popen, handoff=None, open_uri=None):
    """Send the prompt along the row's path. Returns (outcome, message) for the status line."""
    if row["kind"] == "cli":
        exe = Path(row["path"])
        if exe.suffix.lower() != ".exe":
            raise RuntimeError(f"{exe.name} çalıştırılamaz: yalnız .exe başlatılır")
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        popen([str(exe), cli_argument(prompt, project_root)], cwd=str(project_root), shell=False,
              creationflags=flags, close_fds=True)
        return "sent", f"{row['label'].split(' — ')[0]} yeni konsolda başladı; istem doğrudan gönderildi."
    if row["kind"] == "handoff":
        handoff_id = handoff(prompt)
        open_uri(f"vscode://{VSCODE_EXTENSION}/handoff?id={quote(handoff_id)}")
        return "handoff", "İstem VS Code'a devredildi; sonuç birazdan burada görünür."
    return "clipboard", "İstem panoya kopyalandı."


# --- Checks ---------------------------------------------------------------------------------------------------

def check_lines(response, shown=8):
    """Readable lines for the check tool's result; a run that did not complete is never shown as clean."""
    if not response.get("ok"):
        return ["Çalışmadı: " + str(response.get("summary", ""))]
    lines = ["Kaydedilmiş dosyalar denetlendi; kaydedilmemiş değişiklikler dahil değil.", "",
             f"{response.get('verified')}: {response.get('summary', '')}"
             + (f"  (kanıt {response['evidence_id']})" if response.get("evidence_id") else "")]
    lines += ["! " + str(w) for w in response.get("warnings", [])]
    findings = response.get("active_findings", response.get("findings", []))
    for finding in findings[:shown]:
        items = finding.get("items") or []
        pos = items[0].get("pos") if items else None
        where = f" @ ({pos['x']}, {pos['y']}) mm" if pos else ""
        lines.append(f"  [{finding.get('severity')}] {finding.get('description')}{where}")
    if len(findings) > shown:
        lines.append(f"  … {len(findings) - shown} bulgu daha (VS Code: PcbAi → ERC ve DRC çalıştır)")
    if response.get("verified") == "checks_incomplete":
        lines.append("Denetim eksik: aşağıdaki zorunlu denetimler tamamlanmadı; sonuç temiz sayılmaz.")
        lines += [f"  {c.get('check_id')}: {c.get('status')} ({c.get('reason')})"
                  for c in response.get("checks_run", []) if c.get("status") != "passed" or c.get("reason")]
    if response.get("waived"):
        lines.append(f"  {len(response['waived'])} bulgu muafiyetli")
    for key, label in (("expired_waivers", "süresi dolmuş muafiyet"), ("orphaned_waivers", "yetim muafiyet"),
                       ("policy_exceeded_waivers", "süre politikasını aşan muafiyet")):
        rows = response.get(key) or []
        if rows:
            lines.append(f"  {len(rows)} {label}: " + ", ".join(r.get("finding_id", "") for r in rows[:shown]))
    return lines


# --- Activity (AJ-7) -------------------------------------------------------------------------------------------

def guidance(event):
    """Same words as pcbai.service.events.guidance; kept here so the window needs no service import."""
    if event.get("outcome") == "blocked":
        return "Ajan değişiklik yapmak istiyor: kartı kaydedip PCB editörünü kapatın, sonra Devam deyin."
    if event.get("outcome") == "ok" and event.get("change_id"):
        return "Ajan dosyayı değiştirdi: KiCad'de Dosya → Geri al (Revert) ile kartı yeniden yükleyin."
    return None


def event_line(event):
    stamp = time.strftime("%H:%M:%S", time.localtime(event.get("time", 0)))
    change = f" · {event['change_id']}" if event.get("change_id") else ""
    return f"{stamp}  {event.get('client')}  {event.get('tool')}  {event.get('outcome')}{change}"


# --- Single instance -------------------------------------------------------------------------------------------

COMMANDS = ("raise", "marker")


def signal_existing(lock, command="raise"):
    """Ask a running window to come to the front ("marker": and focus the marker note). True when it answered."""
    try:
        info = json.loads(Path(lock).read_text(encoding="utf-8"))
        with socket.create_connection(("127.0.0.1", int(info["port"])), timeout=1.0) as conn:
            conn.sendall(f"{command} {info['token']}\n".encode())
            return conn.recv(16).decode().strip() == "ok"
    except (OSError, ValueError, KeyError, TypeError):
        return False


def claim(lock):
    """Listen for "raise" requests and write the lock file. Returns (listener, token)."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)
    token = secrets.token_hex(16)
    Path(lock).parent.mkdir(parents=True, exist_ok=True)
    Path(lock).write_text(json.dumps({"pid": os.getpid(), "port": listener.getsockname()[1], "token": token}),
                          encoding="utf-8")
    return listener, token


def accept_raise(listener, token, on_raise):
    """Serve raise requests until the listener closes; a wrong token is refused. Calls ``on_raise(command)``."""
    while True:
        try:
            conn, _ = listener.accept()
        except OSError:
            return
        with conn:
            line = conn.recv(256).decode(errors="replace").strip()
            command = next((c for c in COMMANDS if line == f"{c} {token}"), None)
            conn.sendall(b"ok\n" if command else b"denied\n")
            if command:
                on_raise(command)


def release(lock):
    try:
        if json.loads(Path(lock).read_text(encoding="utf-8")).get("pid") == os.getpid():
            Path(lock).unlink()
    except (OSError, ValueError):
        pass
