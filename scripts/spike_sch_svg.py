"""S8: measure schematic SVG ↔ sheet mm, pin geometry and netlist-backed net highlighting on real demos."""

import argparse
import json
import math
import random
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli, run
from pcbai.kicad.files import revision, within
from pcbai.sch.scene import parse_netlist, scene_sch
from pcbai.sch_render import render_sch
from pcbai.view_render import apply_matrix, svg_metadata
from scripts.evidence_output import report_path

ROOT = Path(__file__).resolve().parents[1]
DEMOS = ["ecc83", "complex_hierarchy", "pic_programmer", "video", "kit-dev-coldfire-xilinx_5213", "stickhub"]


def vertices(path):
    """Every coordinate pair KiCad drew as a path/line vertex on this page."""
    svg, _ = svg_metadata(path)
    found = []
    for node in svg.iter():
        tag = node.tag.split("}")[-1]
        if tag == "path":
            numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", node.get("d", ""))]
            found.extend(zip(numbers[0::2], numbers[1::2], strict=False))
        elif tag == "line":
            found.extend([(float(node.get("x1")), float(node.get("y1"))),
                          (float(node.get("x2")), float(node.get("y2")))])
    grid = {}
    for x, y in found:
        grid.setdefault((round(x), round(y)), []).append((x, y))
    return grid


def nearest(grid, p):
    best = math.inf
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for q in grid.get((round(p[0]) + dx, round(p[1]) + dy), []):
                best = min(best, math.dist(p, q))
    return best


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="Explicitly replace published S8 evidence")
    args = parser.parse_args()
    evidence = report_path(ROOT, "S8-result.json", publish=args.publish)
    try:
        cli = Path(find_kicad_cli())
    except PcbAiError as exc:
        print("SKIP: " + str(exc))
        return 77
    demos = cli.parent.parent / "share/kicad/demos"
    rng = random.Random(8)
    results = []
    with tempfile.TemporaryDirectory(prefix="pcbai-s8-") as tmp:
        for demo in DEMOS:
            copy = Path(tmp) / demo
            shutil.copytree(demos / demo, copy)
            project = next(copy.glob("*.kicad_pro"))
            document = project.with_suffix(".kicad_sch").name
            before = revision(copy)
            started = time.perf_counter()
            report = render_sch(copy, document, before, Path(tmp) / "views" / demo)
            render_seconds = time.perf_counter() - started
            netlist = parse_netlist(Path(report["netlist"]).read_bytes())
            pin_errors, body_errors, identity_errors, page_rows = [], [], [], []
            highlighted = {}
            started = time.perf_counter()
            for page in report["pages"]:
                scene = scene_sch(within(copy, page["document"]).read_bytes(), page["instance"], netlist)
                grid = vertices(page["path"])
                for corner in ([0, 0], [100, 100]):
                    identity_errors.append(math.dist(apply_matrix(page["mm_to_svg"], corner), corner))
                pins = [i for i in scene["items"] if i["type"] == "pin"]
                drawn = [p for p in pins if not p["hidden"] and math.dist(*p["points"]) > 0.01]
                # The connection point is electrical; the body end is shortened by inverted/clock styles.
                errors = [nearest(grid, apply_matrix(page["mm_to_svg"], p["at"])) for p in drawn]
                body = [nearest(grid, apply_matrix(page["mm_to_svg"], p["points"][1])) for p in drawn]
                pin_errors.extend(errors)
                body_errors.extend(body)
                for pin in pins:
                    if pin["net"]:
                        highlighted.setdefault(pin["net"], set()).add((pin["reference"], pin["number"]))
                wires = [i for i in scene["items"] if i["type"] == "wire"]
                page_rows.append(dict(page=page["names"], document=page["document"], symbols=sum(
                    i["type"] == "symbol" for i in scene["items"]), pins=len(pins), drawn_pins=len(drawn),
                    max_pin_error_mm=max(errors, default=0), wires=len(wires),
                    wires_with_net=sum(bool(w["net"]) for w in wires), warnings=scene["warnings"]))
            scene_seconds = time.perf_counter() - started
            members = {name: {(m["reference"], m["pin"]) for m in nodes} for name, nodes in netlist["members"].items()}
            sample = rng.sample(sorted(netlist["pins"]), min(20, len(netlist["pins"])))
            net_checks = []
            for key in sample:
                name = netlist["pins"][key]
                net_checks.append(dict(reference=key[0], pin=key[1], net=name,
                                       equal=highlighted.get(name, set()) == members[name]))
            all_equal = sum(highlighted.get(n, set()) == m for n, m in members.items())
            if revision(copy) != before:
                raise RuntimeError("Source revision changed")
            results.append(dict(
                demo=demo, pages=len(report["pages"]), render_seconds=round(render_seconds, 2),
                scene_seconds=round(scene_seconds, 2), drawn_pins=len(pin_errors),
                max_pin_error_mm=max(pin_errors, default=None),
                pins_over_0_05_mm=sum(e > 0.05 for e in pin_errors),
                body_ends_matching=sum(e <= 0.05 for e in body_errors),
                max_identity_deviation_mm=max(identity_errors),
                sampled_pins_net_equal=sum(c["equal"] for c in net_checks), sampled_pins=len(net_checks),
                nets_equal=all_equal, nets=len(members), page_details=page_rows, samples=net_checks,
                source_revision_unchanged=True))
            row = {k: v for k, v in results[-1].items() if k not in {"page_details", "samples"}}
            print(json.dumps(row, ensure_ascii=False))
    version = run([cli, "--version"], timeout=15).stdout.strip()
    evidence.write_text(json.dumps(dict(kicad_version=version, tolerance_mm=0.05, demos=results),
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print("Kanıt:", evidence)
    failed = [r["demo"] for r in results if r["pins_over_0_05_mm"] or r["sampled_pins_net_equal"] != r["sampled_pins"]]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
