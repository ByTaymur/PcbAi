"""Install the PcbAi PCM ZIP the way KiCad's "Install from File…" does, while KiCad is closed.

    python kicad_plugin/install_pcm.py dist/pcbai-kicad-<ver>.zip [--enable-api]

- Extracts plugins/* to <Documents>/KiCad/<ver>/3rdparty/plugins/org_pcbai_kicad and resources/icon.png to
  3rdparty/resources/org_pcbai_kicad (only the package's own entries; no path escapes).
- Records the package in <config>/installed_packages.json with repository "<LOCAL>", as KiCad does for files.
- Moves an old hand-copied <Documents>/KiCad/<ver>/plugins/org.pcbai.kicad into the backup folder (same
  identifier twice would conflict); nothing is deleted.
- --enable-api sets api.enable_server in kicad_common.json (Preferences → Plugins → Enable KiCad API).
Every changed settings file is copied to .pcbai-state/kicad-install-backup-<time> first.
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
IDENTIFIER = "org.pcbai.kicad"
FOLDER = IDENTIFIER.replace(".", "_")


def kicad_running():
    if os.name != "nt":
        return False
    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=15).stdout
    names = {row[0].lower() for row in csv.reader(out.splitlines()) if row}
    return bool(names & {"kicad.exe", "pcbnew.exe", "eeschema.exe"})


def dump_like(raw, value):
    """Serialise ``value`` with the indentation and newlines of ``raw`` (KiCad uses 2 or 4 spaces, CRLF on Windows)."""
    newline = "\r\n" if b"\r\n" in raw else "\n"
    original = json.loads(raw)
    for indent in (4, 2):
        text = json.dumps(original, indent=indent, ensure_ascii=False).replace("\n", newline)
        if text.encode("utf-8").rstrip() == raw.rstrip():
            trailing = raw[len(raw.rstrip()):].decode("utf-8")
            return (json.dumps(value, indent=indent, ensure_ascii=False).replace("\n", newline) + trailing).encode()
    return (json.dumps(value, indent=2, ensure_ascii=False).replace("\n", newline) + newline).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--enable-api", action="store_true")
    parser.add_argument("--version", default="10.0")
    args = parser.parse_args()
    if kicad_running():
        raise SystemExit("KiCad is running; close it first (its settings would overwrite this install).")
    documents = Path(os.environ.get("KICAD_DOCUMENTS_HOME") or Path.home() / "Documents" / "KiCad") / args.version
    config = Path(os.environ.get("APPDATA", Path.home() / ".config")) / "kicad" / args.version
    third = documents / "3rdparty"
    with zipfile.ZipFile(args.package) as archive:
        metadata = json.loads(archive.read("metadata.json"))
        if metadata.get("identifier") != IDENTIFIER or metadata.get("type") != "plugin":
            raise SystemExit("Not the PcbAi plugin package")
        version = metadata["versions"][0]["version"]
        members = []
        for info in archive.infolist():
            name = PurePosixPath(info.filename)
            if info.is_dir() or name.as_posix() == "metadata.json":
                continue
            if name.is_absolute() or ".." in name.parts or name.parts[0] not in {"plugins", "resources"}:
                raise SystemExit(f"Unexpected package entry: {info.filename}")
            members.append(info)
        backup = ROOT / ".pcbai-state" / time.strftime("kicad-install-backup-%Y%m%d-%H%M%S")
        backup.mkdir(parents=True)
        for name in ("installed_packages.json", "kicad_common.json"):
            if (config / name).is_file():
                shutil.copy2(config / name, backup / name)
        old = documents / "plugins" / IDENTIFIER
        if old.is_dir():
            shutil.move(str(old), str(backup / ("old-plugins-" + IDENTIFIER)))
        targets = {"plugins": third / "plugins" / FOLDER, "resources": third / "resources" / FOLDER}
        for target in targets.values():
            if target.exists():
                shutil.move(str(target), str(backup / ("previous-" + target.parent.name + "-" + FOLDER)))
            target.mkdir(parents=True)
        for info in members:
            name = PurePosixPath(info.filename)
            destination = targets[name.parts[0]].joinpath(*name.parts[1:])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(info))
    record_path = config / "installed_packages.json"
    raw = record_path.read_bytes() if record_path.is_file() else b'{\n    "packages": []\n}\n'
    records = json.loads(raw)
    records["packages"] = [p for p in records.get("packages", []) if p.get("package", {}).get("identifier") != IDENTIFIER]
    records["packages"].append(dict(current_version=version, install_timestamp=int(time.time()), package=metadata,
                                    pinned=False, repository_id="<LOCAL>", repository_name="<LOCAL>"))
    record_path.write_bytes(dump_like(raw, records))
    if args.enable_api:
        common_path = config / "kicad_common.json"
        raw = common_path.read_bytes()
        common = json.loads(raw)
        common.setdefault("api", {})["enable_server"] = True
        common_path.write_bytes(dump_like(raw, common))
    print(json.dumps(dict(installed=version, plugin=str(targets["plugins"]), resources=str(targets["resources"]),
                          api_enabled=args.enable_api, backup=str(backup)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
