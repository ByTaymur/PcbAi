"""S7: measure real SVG pad centres and prepare isolated fixtures for viewer acceptance."""

import argparse
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli, run
from pcbai.tools.engine import Engine
from pcbai.view_render import apply_matrix, svg_metadata
from scripts.evidence_output import report_path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true', help='Explicitly replace published S7 evidence')
    args = parser.parse_args()
    evidence_report = report_path(ROOT, 'S7-result.json', publish=args.publish)
    output = ROOT / ".pcbai-state/s7"
    output.mkdir(parents=True, exist_ok=True)
    try:
        cli = Path(find_kicad_cli())
    except PcbAiError as exc:
        print("SKIP: " + str(exc))
        return 77
    demos = cli.parent.parent / "share/kicad/demos"
    measurements = []
    fixtures = []
    with tempfile.TemporaryDirectory(prefix="pcbai-s7-") as tmp:
        for demo in ["ecc83", "interf_u", "pic_programmer"]:
            copy = Path(tmp) / demo
            shutil.copytree(demos / demo, copy)
            project = next(copy.glob("*.kicad_pro"))
            document = project.with_suffix(".kicad_pcb").name
            engine = Engine([project], output)
            session = next(iter(engine.sessions.entries.values()))
            target = session.target(document)
            scene = engine.call("scene_pcb", target)
            render = engine.call("render_pcb", dict(target, layers=["F.Cu", "B.Cu", "F.SilkS", "Edge.Cuts"]))
            drc = engine.call("drc", target)
            for response in [scene, render, drc]:
                if not response["ok"]:
                    raise RuntimeError(response)
            report = render["render"]
            circles = []
            for layer in report["layers"][:2]:
                svg, _ = svg_metadata(layer["path"])
                circles.extend(
                    [
                        [float(n.get("cx")), float(n.get("cy"))]
                        for n in svg.iter()
                        if n.tag.split("}")[-1] == "circle"
                    ]
                )
            pads = [i for i in scene["scene"]["items"] if i["type"] == "pad" and i["shape"] == "circle"]
            if len(pads) < 3:
                raise RuntimeError("Too few independent circular pad samples")
            errors = []
            samples = []
            for pad in pads:
                expected = apply_matrix(report["mm_to_svg"], pad["at"])
                observed = min(circles, key=lambda p: math.dist(expected, p))
                recovered = apply_matrix(report["svg_to_mm"], observed)
                error = math.dist(recovered, pad["at"])
                errors.append(error)
                samples.append(
                    dict(
                        reference=pad["reference"],
                        pad=pad["number"],
                        mm=pad["at"],
                        svg=observed,
                        recovered_mm=recovered,
                        error_mm=error,
                    )
                )
            if max(errors) > 0.05:
                raise RuntimeError(f"S7 {demo}: error {max(errors)} exceeds 0.05 mm")
            if session.target(document) != target:
                raise RuntimeError("Source revision changed")
            fixture = dict(
                demo=demo,
                document=document,
                revision=target["revision"],
                scene=scene["scene"],
                render=report,
                findings=drc["findings"],
                summary=drc["summary"],
                evidence=drc["evidence_id"],
            )
            fixture_path = output / (demo + ".json")
            fixture_path.write_text(
                json.dumps(fixture, ensure_ascii=False, allow_nan=False), encoding="utf-8"
            )
            fixtures.append(str(fixture_path))
            measurements.append(
                dict(
                    demo=demo,
                    circular_pads=len(pads),
                    footprint_count=sum(i["type"] == "footprint" for i in scene["scene"]["items"]),
                    max_error_mm=max(errors),
                    matrix=report["mm_to_svg"],
                    samples=samples,
                    source_revision_unchanged=True,
                )
            )
    version = run([cli, "--version"], timeout=15).stdout.strip()
    result = dict(kicad_version=version, tolerance_mm=0.05, boards=measurements, fixtures=fixtures)
    evidence_report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            dict(
                kicad_version=version,
                boards=[{k: v for k, v in m.items() if k != "samples"} for m in measurements],
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
