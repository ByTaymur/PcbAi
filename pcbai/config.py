import os
import json
from pathlib import Path

from pcbai.external import run
from pcbai.core.contract import PcbAiError
from pcbai.kicad.files import atomic_write
from pcbai.permissions import private_windows_acl, windows_owner


def private_directory(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
        raise PcbAiError("unsafe_state", "State directory cannot be a symbolic link")
    marker = path / ".pcbai-owned-state"
    if any(path.iterdir()) and (not marker.is_file() or marker.read_text(encoding="ascii") != "pcbai-state-v1"):
        raise PcbAiError("unsafe_state", "Existing nonempty state directory is not managed by PcbAi; choose an empty directory")
    children = [path]
    pending = [path]
    while pending:
        for entry in pending.pop().iterdir():
            if entry.is_symlink() or getattr(entry.lstat(), "st_file_attributes", 0) & 0x400:
                raise PcbAiError("unsafe_state", "State directory contains a symlink or junction")
            children.append(entry)
            if entry.is_dir():
                pending.append(entry)
    if os.name == "nt":
        # Use the current user's SID, avoiding locale-dependent group/user names.
        who = run(["whoami", "/user", "/fo", "csv", "/nh"], timeout=10)
        import csv
        if who.returncode:
            raise PcbAiError("unsafe_state", "Cannot identify current user SID")
        sid = next(csv.reader(who.stdout.strip().splitlines()))[-1]
        if windows_owner(path) != sid:
            raise PcbAiError("unsafe_state", "State directory must be owned by the current user")
        private_windows_acl(children, sid)
    else:
        if path.stat().st_uid != os.getuid():
            raise PcbAiError("unsafe_state", "State directory must be owned by the current user")
        for entry in children:
            entry.chmod(0o700 if entry.is_dir() else 0o600)
    if not marker.exists():
        marker.write_text("pcbai-state-v1", encoding="ascii")
        if os.name != "nt":
            marker.chmod(0o600)
    return path.resolve()


def validate_state_location(state, project_roots):
    expanded = Path(state).expanduser()
    raw = Path(os.path.abspath(expanded))
    resolved = expanded.resolve()
    for project in project_roots:
        root = Path(project).expanduser().resolve()
        if any(path.is_relative_to(root) or root.is_relative_to(path) for path in (raw, resolved)):
            raise PcbAiError("invalid_state_directory",
                "Service state must be outside every registered project and must not contain a project; "
                "choose a separate PCBAI_STATE_DIR or use the default location")
    return resolved


def state_directory(project_roots=()):
    configured = os.environ.get("PCBAI_STATE_DIR")
    base = Path(configured) if configured else Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "PcbAi"
    base = base.expanduser()
    validate_state_location(base, project_roots)
    return private_directory(base)


def write_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8"))
    if os.name != "nt":
        Path(path).chmod(0o600)
