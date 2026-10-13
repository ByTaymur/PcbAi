"""G5: where does a board view refresh spend its time after a saved value change? Disposable demo copies only."""

import argparse
import json
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli, run
from pcbai.kicad import exports
from pcbai.tools.engine import Engine
from scripts.evidence_output import report_path

ROOT = Path(__file__).resolve().parents[1]


def percentile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()
    evidence = report_path(ROOT, "G5-result.json", publish=args.publish)
    try:
        cli = Path(find_kicad_cli())
    except PcbAiError as exc:
        print("SKIP: " + str(exc))
        return 77
    demos = cli.parent.parent / "share/kicad/demos"
    boards = []
    with tempfile.TemporaryDirectory(prefix="pcbai-g5-") as tmp:
        for demo in ["ecc83", "pic_programmer"]:
            copy = Path(tmp) / demo
            shutil.copytree(demos / demo, copy)
            project = next(copy.glob("*.kicad_pro"))
            document = project.with_suffix(".kicad_pcb").name
            state = Path(tmp) / ("state-" + demo)
            state.mkdir()
            engine = Engine([project], state)
            session = next(iter(engine.sessions.entries.values()))
            board = copy / document
            original = board.read_bytes()
            calls = []
            real = exports.run

            def counted(argv, real=real, calls=calls, **kwargs):
                started = time.perf_counter()
                try:
                    return real(argv, **kwargs)
                finally:
                    calls.append(time.perf_counter() - started)

            rows = []
            with patch.object(exports, "run", counted):
                for index in range(args.runs):
                    # A saved change: new bytes, therefore a new project revision and a cache miss.
                    board.write_bytes(original + b"\n" * (index + 1))
                    calls.clear()
                    t0 = time.perf_counter()
                    status = engine.call("pcbai_status", {})
                    revision = next(s for s in status["sessions"] if s["id"] == session.id)["revision"]
                    t1 = time.perf_counter()
                    target = dict(session=session.id, document=document, revision=revision)
                    scene = engine.call("scene_pcb", target)
                    t2 = time.perf_counter()
                    render = engine.call("render_pcb", target)
                    t3 = time.perf_counter()
                    markers = engine.call("get_markers", {"session": session.id})
                    t4 = time.perf_counter()
                    for response in (scene, render, markers):
                        if not response["ok"]:
                            raise RuntimeError(response)
                    rows.append(dict(status_s=t1 - t0, scene_s=t2 - t1, render_s=t3 - t2, markers_s=t4 - t3,
                                     total_s=t4 - t0, cli_calls=len(calls), cli_s=sum(calls),
                                     layers=len(render["render"]["layers"])))
            board.write_bytes(original)
            totals = [r["total_s"] for r in rows]
            summary = {k: round(statistics.median(r[k] for r in rows), 3)
                       for k in ("status_s", "scene_s", "render_s", "markers_s", "cli_s", "cli_calls")}
            boards.append(dict(demo=demo, runs=len(rows), p50_s=round(percentile(totals, .5), 3),
                               p95_s=round(percentile(totals, .95), 3), median_parts=summary, rows=rows))
            print(json.dumps({k: v for k, v in boards[-1].items() if k != "rows"}, ensure_ascii=False))
    version = run([cli, "--version"], timeout=15).stdout.strip()
    evidence.write_text(json.dumps(dict(kicad_version=version, note="Service-side refresh; excludes webview "
                                        "image decode and the 1 s change poll", boards=boards), indent=2),
                        encoding="utf-8")
    print("Kanıt:", evidence)
    return 0


if __name__ == "__main__":
    sys.exit(main())
