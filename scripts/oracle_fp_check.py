"""Compare plan_move (byte-preserving) with KiCad's own pcbnew Rotate/Flip/SetPosition on demo boards."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pcbai.external import find_kicad_cli
from pcbai.pcb.edit import plan_moves
from pcbai.sch.model import footprints
from scripts.evidence_output import report_path
from scripts.oracle.compare_fp import differences

ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / "scripts/oracle/pcbnew_edit.py"


def kicad_python():
    cli = Path(find_kicad_cli())
    candidate = cli.parent / ("python.exe" if cli.suffix == ".exe" else "python3")
    return candidate if candidate.is_file() else None


def operations(board):
    ops = []
    for index, fp in enumerate(footprints(board)):
        reference = fp.get("Reference")
        if not reference or reference.startswith("#") or any(o["reference"] == reference for o in ops):
            continue
        at = fp["at"]
        side = "back" if (fp.get("layer") or "F.Cu").startswith("B.") else "front"
        other = "front" if side == "back" else "back"
        kind = index % 4
        op = dict(reference=reference, x=None, y=None, rotation=None, side=None)
        if kind == 0:
            op.update(x=round(at[0] + 1.27, 4), y=round(at[1] - 2.54, 4))
        elif kind == 1:
            op.update(rotation=((at[2] if len(at) > 2 else 0) + 90 + 180) % 360 - 180)
        elif kind == 2:
            op.update(side=other)
        else:
            op.update(side=other, rotation=30.0, x=round(at[0] - 0.5, 4))
        ops.append(op)
    return ops


def check(board_path, workdir, python):
    original = board_path.read_bytes()
    ops = operations(original)
    spec = workdir / "ops.json"
    spec.write_text(json.dumps(ops), encoding="utf-8")
    oracle = workdir / "oracle.kicad_pcb"
    process = subprocess.run([str(python), str(ORACLE), str(board_path), str(oracle), str(spec)],
                             capture_output=True, text=True, timeout=300, shell=False)
    if process.returncode:
        raise RuntimeError(process.stderr[-2000:])
    planned = plan_moves(original, ops, skip_unsupported=True)
    ours, refused = planned["data"], planned["refused"]
    problems = differences(ours, oracle.read_bytes())
    refused_refs = {r for r, _ in refused}
    # Footprints we refused are expected to differ from the oracle; report them separately.
    return dict(ops=len(ops), refused=refused, problems=[p for p in problems if p[0] not in refused_refs],
                changed_bytes=sum(a != b for a, b in zip(original, ours, strict=False)) + abs(len(original) - len(ours)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("demos", nargs="*", default=["ecc83", "interf_u", "pic_programmer", "video", "stickhub"])
    args = parser.parse_args()
    python = kicad_python()
    if python is None:
        print("SKIP: KiCad Python not found")
        return 77
    demos = Path(find_kicad_cli()).parent.parent / "share/kicad/demos"
    results = []
    with tempfile.TemporaryDirectory(prefix="pcbai-oracle-") as tmp:
        for demo in args.demos:
            copy = Path(tmp) / demo
            shutil.copytree(demos / demo, copy)
            for board in sorted(copy.glob("*.kicad_pcb")):
                work = Path(tmp) / (demo + "-" + board.stem)
                work.mkdir()
                outcome = check(board, work, python)
                outcome.update(demo=demo, board=board.name)
                results.append(outcome)
                print(json.dumps(dict(demo=demo, board=board.name, ops=outcome["ops"], refused=len(outcome["refused"]),
                                      problems=len(outcome["problems"])), ensure_ascii=False))
                for problem in outcome["problems"][:6]:
                    print("   ", problem)
    path = report_path(ROOT, "pcb-edit-oracle.json", publish=args.publish)
    path.write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 1 if any(r["problems"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
