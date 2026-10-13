"""Measure optional engines on isolated KiCad demo copies. No inferred success or default engine."""
import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pcbai.external import find_kicad_cli  # noqa: E402
from pcbai.kicad.files import digest  # noqa: E402
from pcbai.tools.engine import Engine  # noqa: E402
from scripts.evidence_output import report_path  # noqa: E402
from scripts.strip_tracks import strip_tracks  # noqa: E402

DEMOS = ["ecc83", "pic_programmer", "video", "interf_u", "stickhub"]


def main():
    # A Windows redirected console may use cp1254; Unicode summaries must not abort a measured run.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engines", nargs="+", choices=["tracemaker", "freerouting"], default=["freerouting", "tracemaker"])
    parser.add_argument("--demos", nargs="+", choices=DEMOS, default=DEMOS)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--work", type=int, default=3000000)
    parser.add_argument("--passes", type=int, default=5)
    parser.add_argument("--repeat", type=int, choices=[1, 2], default=2)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = report_path(ROOT, "engines-result.json", publish=args.publish, output=args.output)
    markdown = report_path(ROOT, output.with_suffix(".md").name, publish=args.publish, output=output.with_suffix(".md"))
    demos = Path(find_kicad_cli()).parent.parent / "share/kicad/demos"
    records = []
    for demo in args.demos:
        folder = demos / demo
        projects = sorted(folder.glob("*.kicad_pro"))
        project = next((p for p in projects if p.stem == demo), projects[0] if projects else None)
        if project is None:
            records.append(dict(demo=demo, status="unavailable", reason="Demo project not installed"))
            continue
        original_hash = digest(project.with_suffix(".kicad_pcb").read_bytes())
        for name in args.engines:
            for repetition in range(args.repeat):
                with tempfile.TemporaryDirectory(prefix="bench-", dir=ROOT / ".pcbai-state") as tmp:
                    root = Path(tmp)
                    shutil.copytree(folder, root / "project")
                    copied = root / "project" / project.name
                    pcb = copied.with_suffix(".kicad_pcb")
                    pcb.write_bytes(strip_tracks(pcb.read_bytes()))
                    state = root / "state"
                    state.mkdir()
                    engine = Engine([copied], state)
                    session = next(iter(engine.sessions.entries.values()))
                    options = {"work": args.work, "threads": 1, "variants": 1} if name == "tracemaker" else {
                        "passes": args.passes, "threads": 1}
                    result = engine.call("autoroute", dict(session.target(pcb.name), mode="preview", engine=name,
                                                           options=options, timeout_seconds=args.timeout))
                    record = dict(demo=demo, engine=name, repetition=repetition, result=result,
                                  source_preserved=digest(project.with_suffix(".kicad_pcb").read_bytes()) == original_hash)
                    # Copies and engine outputs stay private; only hashes/measurements are retained in result.
                    engine.jobs.close()
                    records.append(record)
                    output.write_text(json.dumps(dict(time=datetime.now(timezone.utc).isoformat(), records=records),
                                                 ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"{demo} / {name} / {repetition + 1}: {result['summary']}", flush=True)
    lines = ["# Motor kıyası", "", "| Demo | Motor | Koşu | Sonuç | Rotalanmamış | DRC | Via | Süre |", "|---|---|---|---|---|---|---|---|"]
    for record in records:
        r = record.get("result", {})
        m = r.get("engine_metrics", {})
        outcome = r.get("engine_run", {})
        status = "ölçüldü" if r.get("ok") else r.get("error", {}).get("code", "unavailable")
        lines.append(f"| {record['demo']} | {record.get('engine', '—')} | {record.get('repetition', '—')} | {status} | "
                     f"{m.get('unconnected_before', '—')} → {m.get('unconnected_after', '—')} | "
                     f"{r.get('drc_before', {}).get('errors', '—')} → {r.get('drc_after', {}).get('errors', '—')} | "
                     f"{m.get('after', {}).get('via_count', '—')} | {outcome.get('seconds', '—')} |")
    lines += ["", "Gerçek motor çıktıları ve DRC kapısı ölçülmeden varsayılan motor seçilmez. Eksik/başarısız koşular kabul değildir."]
    markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if all(r.get("result", {}).get("ok") and r.get("source_preserved") for r in records) else 1


if __name__ == "__main__":
    sys.exit(main())
