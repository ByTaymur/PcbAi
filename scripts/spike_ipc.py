"""Opt-in S1 probe: own two hidden GUI processes, copied demos and isolated settings.

Run: python scripts/spike_ipc.py --run --output docs/spikes/S1-result.json
No user board, user setting, or existing GUI process is changed or terminated.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# A standalone script can also be run before editable installation.
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pcbai.external import find_kicad_cli, run  # noqa: E402
from pcbai.config import private_directory  # noqa: E402
from pcbai.kicad.discover import request  # noqa: E402
from pcbai.kicad.files import digest  # noqa: E402


def config_hashes(directory):
    return {p.relative_to(directory).as_posix(): digest(p.read_bytes())
            for p in directory.rglob("*") if p.is_file()}


def probe():
    cli = Path(find_kicad_cli())
    version = run([cli, "--version"], timeout=15).stdout.strip()
    major_minor = ".".join(version.split(".")[:2])
    executable = cli.parent / ("pcbnew.exe" if os.name == "nt" else "pcbnew")
    if not executable.is_file():
        raise RuntimeError("Configured KiCad installation has no PCB editor")
    user_config = Path(os.environ.get("APPDATA", Path.home() / ".config")) / "kicad" / major_minor
    before = config_hashes(user_config)
    workspace = REPO / ".pcbai-state"
    if workspace.exists() and (workspace.is_symlink() or getattr(workspace.lstat(), "st_file_attributes", 0) & 0x400):
        raise RuntimeError("Test workspace must not be a symlink or junction")
    workspace.mkdir(exist_ok=True)
    workspace.resolve().relative_to(REPO.resolve())
    result = dict(kicad=version, s1_complete=False, s3_complete=False, instances=[], failed_probes=[])
    failures = {}
    with tempfile.TemporaryDirectory(prefix="ipc-spike-", dir=workspace) as temporary:
        root = Path(temporary).resolve()
        root.relative_to(workspace.resolve())  # Verify recursive cleanup remains in the intended workspace.
        private_directory(root)
        config = root / "config" / major_minor
        config.mkdir(parents=True)
        # Copy configuration files as data, avoiding user's plugin/script directories.
        for name in ("kicad_common.json", "pcbnew.json", "fp-lib-table", "sym-lib-table"):
            source = user_config / name
            if source.is_file():
                shutil.copyfile(source, config / name)
        common_path = config / "kicad_common.json"
        common = json.loads(common_path.read_text(encoding="utf-8")) if common_path.exists() else {}
        common.setdefault("api", {})["enable_server"] = True
        common.setdefault("system", {})["working_dir"] = str(root)
        common_path.write_text(json.dumps(common), encoding="utf-8")
        ipc_temp = root / "tmp"
        ipc_temp.mkdir()
        env = dict(os.environ, KICAD_CONFIG_HOME=str(root / "config"), KICAD_DOCUMENTS_HOME=str(root / "documents"),
                   TEMP=str(ipc_temp), TMP=str(ipc_temp), PYTHONPATH=str(REPO))
        env.pop("KICAD_API_SOCKET", None)
        env.pop("KICAD_API_TOKEN", None)
        processes, projects = [], []
        try:
            for index in range(2):
                project = root / f"project-{index + 1}"
                shutil.copytree(cli.parent.parent / "share/kicad/demos/ecc83", project)
                board = next(project.glob("*.kicad_pcb"))
                startup = subprocess.STARTUPINFO() if os.name == "nt" else None
                if startup is not None:
                    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startup.wShowWindow = subprocess.SW_HIDE
                process = subprocess.Popen([str(executable), str(board)], env=env, cwd=project, shell=False,
                                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           startupinfo=startup)
                processes.append(process)
                projects.append((project, board))
                # Give the first instance a chance to claim the default socket.
                if index == 0:
                    time.sleep(1)
            sockets = ["ipc://" + str(ipc_temp / "kicad/api.sock")]
            sockets.extend("ipc://" + str(ipc_temp / "kicad" / f"api-{p.pid}.sock") for p in processes)
            found = {}
            deadline = time.monotonic() + 35
            while time.monotonic() < deadline and len(found) < 2:
                for socket in sockets:
                    if socket in found:
                        continue
                    try:
                        # Worker uses this explicit socket and no token. Its lifetime is bounded.
                        output = request(socket, "discover", worker_env=env)
                        if output["documents"]:
                            found[socket] = output
                    except Exception as exc:
                        key = (Path(socket[6:]).name, str(exc))
                        failures[key] = failures.get(key, 0) + 1
                if len(found) < 2:
                    time.sleep(0.5)
            for socket, output in found.items():
                for project, board in projects:
                    project_file = next(project.glob("*.kicad_pro"))
                    if any(Path(d["project"]).resolve() == project_file for d in output["documents"]):
                        live = request(socket, "summary", worker_env=env, project=str(project_file), board=str(board))
                        selection = request(socket, "selection", worker_env=env, project=str(project_file), board=str(board))
                        contents = live["contents"].encode("utf-8")
                        result["instances"].append(dict(socket=Path(socket[6:]).name, project=project.name,
                                                         open_pcb_count=len(output["documents"]), token_required=False,
                                                         live_sha256=digest(contents), saved_sha256=digest(board.read_bytes()),
                                                         buffer_matches_saved_bytes=contents == board.read_bytes(),
                                                         selection_count=len(selection["selection"]),
                                                         lock_files=[p.name for p in project.glob("*.lck")]))
            result["s1_complete"] = len(result["instances"]) == 2
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()  # Only processes created above; no name-based termination.
                process.wait(timeout=10)
    result["user_config_unchanged"] = config_hashes(user_config) == before
    result["failed_probes"] = [dict(socket=socket, error=message, attempts=count)
                               for (socket, message), count in failures.items()]
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Launch two isolated test PCB editors")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument('--publish', action='store_true', help='Allow writing a published docs/spikes report')
    args = parser.parse_args()
    if not args.run:
        parser.error("--run is required to launch the isolated GUI experiment")
    from scripts.evidence_output import report_path
    output_path = report_path(REPO, args.output.name, publish=args.publish, output=args.output)
    output = probe()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=True, indent=2))
