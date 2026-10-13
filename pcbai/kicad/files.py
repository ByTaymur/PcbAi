import hashlib
import csv
import os
import tempfile
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


def project_files(root):
    root = Path(root).resolve()
    files = []
    for path in root.rglob("*"):
        parts = path.relative_to(root).parts
        if any(part in {".git", "__pycache__", ".venv"} for part in parts):
            continue
        if parts[0] == "pcbai" and (len(parts) < 2 or parts[1] != "lib"):
            continue
        # SPICE models are simulation inputs: they belong to the snapshot and to the revision.
        if path.is_file() and (path.suffix.startswith(".kicad_") or path.suffix.lower() in {".step", ".wrl", ".cir"} | SPICE
                               or path.name in {"sym-lib-table", "fp-lib-table"}):
            within(root, str(path.relative_to(root)))
            files.append(path)
    return sorted(files)


def revision(root):
    hasher = hashlib.sha256()
    for path in project_files(root):
        hasher.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        hasher.update(bytes.fromhex(digest(path.read_bytes())))
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
    if editors:
        raise PcbAiError("editor_open", "Close KiCad including the project manager before file-mode changes")


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
