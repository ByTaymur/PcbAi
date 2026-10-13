"""Isolated live-KiCad lab: own hidden PCB editors on demo copies with a private, API-enabled configuration.

Used by the S1/S3/G6 experiments. Never touches the user's KiCad settings, boards or running processes:
settings are copied as data into a private temporary KICAD_CONFIG_HOME, and only processes started here are
terminated (by handle, never by name).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pcbai.config import private_directory  # noqa: E402
from pcbai.external import find_kicad_cli, private_kicad_config, run  # noqa: E402
from pcbai.kicad.discover import request  # noqa: E402
from pcbai.kicad.files import digest  # noqa: E402


def config_hashes(directory):
    return {p.relative_to(directory).as_posix(): digest(p.read_bytes())
            for p in directory.rglob("*") if p.is_file()} if directory.is_dir() else {}


class Lab:
    def __init__(self, root, cli, env, sockets_dir):
        self.root, self.cli, self.env, self.sockets_dir = root, cli, env, sockets_dir
        self.processes, self.boards = [], []

    def copy_demo(self, demo, name):
        project = self.root / name
        shutil.copytree(self.cli.parent.parent / "share/kicad/demos" / demo, project)
        return project

    def open_board(self, board, delay=1.0):
        executable = self.cli.parent / ("pcbnew.exe" if os.name == "nt" else "pcbnew")
        startup = None
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = subprocess.SW_HIDE
        process = subprocess.Popen([str(executable), str(board)], env=self.env, cwd=board.parent, shell=False,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   startupinfo=startup)
        self.processes.append(process)
        self.boards.append(board)
        time.sleep(delay)
        return process

    def sockets(self):
        folder = self.sockets_dir / "kicad"
        return sorted("ipc://" + str(p) for p in folder.glob("api*.sock")) if folder.is_dir() else []

    def call(self, socket, action, **kwargs):
        return request(socket, action, worker_env=self.env, **kwargs)

    def wait_documents(self, count, timeout=60):
        """Poll every socket until ``count`` sockets report an open PCB; returns {socket: discover output}."""
        found, failures = {}, {}
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and len(found) < count:
            for socket in self.sockets():
                if socket in found:
                    continue
                try:
                    output = self.call(socket, "discover")
                    if output["documents"]:
                        found[socket] = output
                except Exception as exc:  # recorded, the experiment reports measured failures
                    key = (Path(socket[6:]).name, str(exc)[:200])
                    failures[key] = failures.get(key, 0) + 1
            if len(found) < count:
                time.sleep(0.5)
        return found, failures


@contextmanager
def lab():
    cli = Path(find_kicad_cli())
    version = run([cli, "--version"], timeout=15).stdout.strip()
    major_minor = ".".join(version.split(".")[:2])
    user_config = Path(os.environ.get("APPDATA", Path.home() / ".config")) / "kicad" / major_minor
    before = config_hashes(user_config)
    workspace = REPO / ".pcbai-state"
    workspace.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="live-lab-", dir=workspace) as temporary:
        root = Path(temporary).resolve()
        root.relative_to(workspace.resolve())
        private_directory(root)
        # A partial copy makes KiCad show its visible first-run setup wizard and wait (measured), so copy the
        # whole settings folder as data, exactly like the kicad-cli isolation does.
        private_kicad_config(cli, root / "config")
        config = root / "config" / major_minor
        common_path = config / "kicad_common.json"
        common = json.loads(common_path.read_text(encoding="utf-8")) if common_path.exists() else {}
        common.setdefault("api", {})["enable_server"] = True
        common.setdefault("system", {})["working_dir"] = str(root)
        common_path.write_text(json.dumps(common), encoding="utf-8")
        sockets = root / "tmp"
        sockets.mkdir()
        env = dict(os.environ, KICAD_CONFIG_HOME=str(root / "config"), KICAD_DOCUMENTS_HOME=str(root / "documents"),
                   TEMP=str(sockets), TMP=str(sockets), PYTHONPATH=str(REPO))
        env.pop("KICAD_API_SOCKET", None)
        env.pop("KICAD_API_TOKEN", None)
        instance = Lab(root, cli, env, sockets)
        instance.version = version
        try:
            yield instance
        finally:
            for process in instance.processes:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
            instance.user_config_unchanged = config_hashes(user_config) == before
