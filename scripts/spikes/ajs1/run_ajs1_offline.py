"""AJ-S1 betik düzeyi ölçüm (KiCad'siz): wx açılışı/ön plan, tek örnek, üst PID ile kapanma, yoklama maliyeti.

    <eklenti venv>\Scripts\python.exe scripts/spikes/ajs1/run_ajs1_offline.py
Ham çıktı: .pcbai-state/ajs1/offline-*.jsonl ve offline-summary.json
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE.parents[2] / ".pcbai-state" / "ajs1"
WIN = str(HERE / "ajs1_window.py")
PY = sys.executable


def rows(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def wait_event(path, event, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        for r in rows(path):
            if r["event"] == event:
                return r
        time.sleep(0.05)
    return None


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    sd = STATE / "offline-lock"
    sd.mkdir(exist_ok=True)
    for f in STATE.glob("offline-*.jsonl"):
        f.unlink()
    log = STATE / "offline-window.jsonl"
    summary = {"python": PY}
    parent = subprocess.Popen([PY, "-c", "import time; time.sleep(600)"])
    t = time.time()
    win = subprocess.Popen([PY, WIN, "--log", str(log), "--state-dir", str(sd), "--parent-pid", str(parent.pid),
                            "--poll-ms", "500"])
    shown = wait_event(log, "shown")
    summary["shown_after_launch_s"] = round(shown["wall"] - t, 3) if shown else None
    fg = wait_event(log, "foreground_check")
    summary["first_open_foreground"] = fg
    time.sleep(5)  # yoklama örnekleri
    log2 = STATE / "offline-second.jsonl"
    t2 = time.time()
    second = subprocess.run([PY, WIN, "--log", str(log2), "--state-dir", str(sd)], timeout=20)
    summary["second_instance_exit_code"] = second.returncode
    summary["second_instance_total_s"] = round(time.time() - t2, 3)
    summary["second_instance_rows"] = rows(log2)
    time.sleep(0.6)
    summary["raise_foreground"] = [r for r in rows(log) if r["event"] == "foreground_check" and r["reason"] == "second_click"]
    polls = [r for r in rows(log) if r["event"] == "poll"]
    summary["polls"] = {"n": len(polls), "ms": [p["ms"] for p in polls], "cpu_ms": [p["cpu_ms"] for p in polls],
                        "errors": sorted({p["error"] for p in polls if p["error"]})}
    tk = time.time()
    parent.kill()
    try:
        win.wait(timeout=10)
        summary["exit_after_parent_kill_s"] = round(time.time() - tk, 3)
    except subprocess.TimeoutExpired:
        summary["exit_after_parent_kill_s"] = None
        win.kill()
    summary["lock_removed"] = not (sd / "ajs1.lock").exists()
    summary["window_events"] = [r["event"] for r in rows(log)]
    (STATE / "offline-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
