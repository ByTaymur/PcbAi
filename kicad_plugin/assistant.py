"""PcbAi Asistan button: start the window in its own process and return at once, so KiCad never waits (AJ-S1)."""
import os
import subprocess
import sys
from pathlib import Path

from pcbai_kicad import run

HERE = Path(__file__).resolve().parent


def launch(*extra):
    windowed = Path(sys.executable).with_name("pythonw.exe")
    python = windowed if windowed.is_file() else Path(sys.executable)
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([str(python), str(HERE / "assistant_window.py"), "--parent-pid", str(os.getppid()), *extra],
                     cwd=str(HERE), shell=False, close_fds=True, creationflags=flags)


if __name__ == "__main__":
    run(launch)
