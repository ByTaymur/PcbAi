import hashlib
import csv
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import run
from pcbai.permissions import preserve_permissions


def digest(data):
    return hashlib.sha256(data).hexdigest()


def within(root, name, *, must_exist=True):
    root = Path(root).resolve()
    candidate = (root / name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PcbAiError("outside_project", "Path resolves outside the registered project") from exc
    if must_exist and not candidate.is_file():
        raise PcbAiError("missing_file", f"File not found: {name}")
    return candidate


SPICE = {".mod", ".lib", ".model", ".sub", ".spice", ".inc", ".ibs", ".sp"}
WAIVER_FILE = "pcbai-waivers.json"
MAX_WAIVER_BYTES = 1024 * 1024


def project_bytes(path):
    """Bound the newly supported JSON policy before hashing or snapshot copying."""
    if path.name != WAIVER_FILE:
        return path.read_bytes()
    with path.open("rb") as stream:
        raw = stream.read(MAX_WAIVER_BYTES + 1)
    if len(raw) > MAX_WAIVER_BYTES:
        raise PcbAiError("invalid_waivers", "Waiver file exceeds the size limit")
    return raw


def project_files(root):
    root = Path(root).resolve()
    policy = root / WAIVER_FILE
    if os.path.lexists(policy):
        resolved = within(root, WAIVER_FILE, must_exist=False)
        if not resolved.is_file() or resolved.stat().st_size > MAX_WAIVER_BYTES:
            raise PcbAiError("invalid_waivers", "Waiver path must be a bounded regular file")
    files = []
    for path in root.rglob("*"):
        parts = path.relative_to(root).parts
        if any(part in {".git", "__pycache__", ".venv"} for part in parts):
            continue
        if parts[0] == "pcbai" and (len(parts) < 2 or parts[1] != "lib"):
            continue
        # SPICE models are simulation inputs: they belong to the snapshot and to the revision.
        if path.is_file() and (path.suffix.startswith(".kicad_") or path.suffix.lower() in {".step", ".wrl", ".cir"} | SPICE
                               or path.name in {"sym-lib-table", "fp-lib-table", "pcbai-waivers.json"}):
            within(root, str(path.relative_to(root)))
            files.append(path)
    return sorted(files)


_DIGESTS = {}
_DIGESTS_LOCK = threading.Lock()
_DIGESTS_LIMIT = 20000


def file_digest(path):
    """SHA-256 of one project file, reused while (inode, size, mtime_ns, ctime_ns) is unchanged (H6).

    Writers here replace files atomically (new inode) and editors update mtime, so a changed file is rehashed; the
    bounded waiver policy is always read again. Large STEP/WRL models are no longer reread on every tool call.
    """
    if path.name == WAIVER_FILE:
        return digest(project_bytes(path))
    info = path.stat()
    key = os.path.normcase(str(path))
    stamp = (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    with _DIGESTS_LOCK:
        cached = _DIGESTS.get(key)
    if cached and cached[0] == stamp:
        return cached[1]
    value = digest(project_bytes(path))
    # Changed while hashing, or so recent that a same-size rewrite could share the timestamp (coarse file system
    # clocks, the "racy git" case): never cache it.
    if path.stat().st_mtime_ns != info.st_mtime_ns or time.time_ns() - info.st_mtime_ns < 2_000_000_000:
        return value
    with _DIGESTS_LOCK:
        if len(_DIGESTS) >= _DIGESTS_LIMIT:
            _DIGESTS.clear()
        _DIGESTS[key] = (stamp, value)
    return value


def revision(root):
    hasher = hashlib.sha256()
    for path in project_files(root):
        hasher.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        hasher.update(bytes.fromhex(file_digest(path)))
    return hasher.hexdigest()


def assert_closed(root):
    locks = [p for p in Path(root).rglob("*") if p.suffix in {".lck", ".lock"} and p.name != ".pcbai-write.lock"]
    if locks:
        raise PcbAiError("editor_open", "Close the KiCad editors before file changes; lock files found")
    if os.name == "nt":
        process = run(["tasklist", "/fo", "csv", "/nh"], timeout=15)
        names = {row[0].lower() for row in csv.reader(process.stdout.splitlines()) if row}
        editors = names & {"eeschema.exe", "pcbnew.exe", "kicad.exe"}
    else:
        process = run(["ps", "-A", "-o", "comm="], timeout=15)
        editors = {Path(name.strip()).name for name in process.stdout.splitlines()} & {"eeschema", "pcbnew", "kicad"}
    if process.returncode:
        raise PcbAiError("editor_state_unknown", "Cannot verify that KiCad editors are closed")
    if editors and editor_check() == "project":
        # H5 opt-in: KiCad's own lock files (checked above) mark this project's open editors; a KiCad process
        # blocks only when its command line names a path inside this project or cannot be read.
        lines = command_lines(editors)
        key = os.path.normcase(str(Path(root).resolve()))
        if lines is None or any(line is None or key in os.path.normcase(line) for line in lines):
            raise PcbAiError("editor_open", "A KiCad process has this project open; close it before file changes")
        return
    if editors:
        raise PcbAiError("editor_open", "Close KiCad including the project manager before file-mode changes")


def editor_check():
    """PCBAI_EDITOR_CHECK: "any" (default, any KiCad process blocks) or "project" (only this project's)."""
    value = os.environ.get("PCBAI_EDITOR_CHECK", "any")
    if value not in {"any", "project"}:
        raise PcbAiError("invalid_configuration", "PCBAI_EDITOR_CHECK must be any or project")
    return value


def command_lines(names):
    """Command lines of running KiCad processes (None entries: unreadable); None when the query fails."""
    if os.name == "nt":
        stems = ",".join("'" + Path(n).stem + "'" for n in sorted(names))
        process = run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                       f"Get-CimInstance Win32_Process | Where-Object {{ @({stems}) -contains "
                       "[IO.Path]::GetFileNameWithoutExtension($_.Name) } | ForEach-Object { "
                       "if ($_.CommandLine) { $_.CommandLine } else { '<unreadable>' } }"], timeout=20)
    else:
        process = run(["ps", "-A", "-o", "args="], timeout=15)
    if process.returncode:
        return None
    rows = [line.strip() for line in process.stdout.splitlines() if line.strip()]
    if os.name != "nt":
        rows = [r for r in rows if Path(r.split()[0]).name in names]
    return [None if r == "<unreadable>" else r for r in rows]


@contextmanager
def write_lock(root, state):
    identity = os.path.normcase(str(Path(root).resolve())).encode("utf-8")
    directory = Path(state) / "locks"
    directory.mkdir(exist_ok=True)
    path = directory / (digest(identity) + ".lock")
    stream = path.open("a+b")
    try:
        try:
            if os.name == "nt":
                import msvcrt
                stream.seek(0)
                if not stream.read(1):
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise PcbAiError("project_busy", "Another PcbAi writer holds this project") from exc
        yield
    finally:
        # Keep the inode/path: deleting a released lock while a new writer has it creates a race.
        # The OS releases this advisory lock on process exit, including crashes.
        stream.close()


def atomic_write(path, data):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".pcbai-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            preserve_permissions(path, temporary)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
