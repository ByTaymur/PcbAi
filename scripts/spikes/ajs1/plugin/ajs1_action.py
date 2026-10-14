"""AJ-S1 düğme girişi: pencereyi ayrık süreçte başlatır ve hemen döner (KiCad bloklanmasın diye).

ajs1_location.json (install_ajs1.py yazar): pencere betiği ve log klasörü.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
t0 = time.perf_counter()
cfg = json.loads((HERE / "ajs1_location.json").read_text(encoding="utf-8"))
state = Path(cfg["state_dir"])
state.mkdir(parents=True, exist_ok=True)
pyw = Path(sys.executable).with_name("pythonw.exe")
exe = str(pyw if pyw.exists() else sys.executable)
args = [exe, cfg["window"], "--log", str(state / "window.jsonl"), "--state-dir", str(state),
        "--parent-pid", str(os.getppid()), "--poll-ms", "500"]
flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
proc = subprocess.Popen(args, creationflags=flags, close_fds=True, shell=False)
with (state / "action.jsonl").open("a", encoding="utf-8") as f:
    f.write(json.dumps({"wall": time.time(), "action_pid": os.getpid(), "ppid": os.getppid(),
                        "python": sys.executable, "child_pid": proc.pid,
                        "env_api": {k: v for k, v in os.environ.items() if k.startswith("KICAD_API")},
                        "ms_to_return": round((time.perf_counter() - t0) * 1000, 1)}) + "\n")
