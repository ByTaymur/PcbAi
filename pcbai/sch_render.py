"""Revision-bound schematic page SVGs. Each page is identified and calibrated by measurement, not by name."""

import json
import re
import secrets
import shutil
import uuid as uuidlib
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli
from pcbai.kicad.cli import snapshot
from pcbai.kicad.exports import command
from pcbai.kicad.files import digest, within
from pcbai.sch.model import _schematic, canonical_id, properties
from pcbai.sch.scene import page_size, parse_netlist
from pcbai.sexpr import Document
from pcbai.view_render import inverse, svg_metadata
from pcbai.views import number

MAX_PAGES = 256


def root_uuid(data):
    node = _schematic(data).root.child("uuid")
    if node is None:
        raise PcbAiError("invalid_document", "Root schematic has no UUID")
    return canonical_id(node.value())


def resolve_pages(root, document, pages):
    """Follow netlist UUID paths through Sheetfile properties to the saved file of every page instance."""
    top = within(root, document)
    top_uuid = root_uuid(top.read_bytes())
    resolved = []
    for page in pages:
        stamps = [s for s in (page["tstamps"] or "").split("/") if s]
        current, relative = top, Path(document)
        for stamp in stamps:
            node = next((n for n in _schematic(current.read_bytes()).root.all("sheet")
                         if n.child("uuid") and canonical_id(n.child("uuid").value()) == canonical_id(stamp)), None)
            if node is None:
                raise PcbAiError("invalid_document", "Netlist sheet path is absent from the saved hierarchy")
            props = properties(node)
            name = props.get("Sheetfile") or props.get("Sheet file")
            if not name:
                raise PcbAiError("invalid_document", "Hierarchical sheet has no file")
            relative = (relative.parent / name.replace("\\", "/"))
            current = within(root, relative.as_posix())
            relative = current.relative_to(Path(root).resolve())
        resolved.append(dict(page, document=Path(relative).as_posix(),
                             instance="/" + top_uuid + ("/" + "/".join(stamps) if stamps else "")))
    return resolved


def export_netlist(copy, document, destination):
    output = copy / "pcbai-netlist.xml"
    command([find_kicad_cli(), "sch", "export", "netlist", within(copy, document), "--format", "kicadxml",
             "--output", output], copy)
    data = output.read_bytes()
    parse_netlist(data)
    Path(destination).write_bytes(data)
    return data


def _calibrate(copy, nonce):
    """Add a page-path text and three circles of distinct radii to every sheet file in the copy."""
    expected = {}
    for sheet in copy.rglob("*.kicad_sch"):
        original = sheet.read_bytes()
        parsed = Document(original)
        if parsed.root.name != "kicad_sch":
            continue
        width, height = page_size(parsed.root)
        points = [[width * 0.25, height * 0.25], [width * 0.75, height * 0.25], [width * 0.25, height * 0.75]]
        radii = [1.234, 2.345, 3.456]
        additions = [f'(text "PCBAICAL{nonce} ${{SHEETPATH}}" (exclude_from_sim no) (at {points[0][0]:.4f} '
                     f'{points[0][1] - 8:.4f} 0) (effects (font (size 1.27 1.27))) (uuid "{uuidlib.uuid4()}"))']
        for (x, y), r in zip(points, radii, strict=True):
            additions.append(f"(circle (center {x:.4f} {y:.4f}) (radius {r}) (stroke (width 0.01) (type solid)) "
                             f'(fill (type none)) (uuid "{uuidlib.uuid4()}"))')
        sheet.write_bytes(original[: parsed.root.end - 1] + "\n".join(additions).encode()
                          + original[parsed.root.end - 1:])
        expected[sheet] = (points, radii)
    return expected


def _measure(path, nonce):
    root, box = svg_metadata(path)
    names = set()
    for node in root.iter():
        text = "".join(node.itertext()) if node.tag.split("}")[-1] == "text" else ""
        match = re.search(r"PCBAICAL" + nonce + r" (\S.*)$", text.strip())
        if match:
            names.add(match.group(1))
    if len(names) != 1:
        raise PcbAiError("invalid_transform", "Schematic SVG page identity is absent or ambiguous")
    circles = [n for n in root.iter() if n.tag.split("}")[-1] == "circle"]
    observed = []
    for radius in (1.234, 2.345, 3.456):
        matches = [c for c in circles if abs(number(c.get("r")) - radius) <= 0.0002]
        if len(matches) != 1:
            raise PcbAiError("invalid_transform", "Schematic calibration circles are ambiguous or absent")
        observed.append([number(matches[0].get("cx")), number(matches[0].get("cy"))])
    return next(iter(names)), observed, box


def render_sch(root, document, revision, destination):
    """Caller serializes this cache and validates source revision before/after."""
    cache = Path(destination) / ("sch-" + digest(document.encode())[:24])
    manifest = cache / "manifest.json"
    if manifest.is_file():
        report = json.loads(manifest.read_text(encoding="utf-8"))
        files = [dict(path=p["path"], sha256=p["sha256"]) for p in report.get("pages", [])]
        files.append(dict(path=report.get("netlist", ""), sha256=report.get("netlist_sha256")))
        if (report.get("document") == document and report.get("revision") == revision
                and all(Path(f["path"]).resolve().is_relative_to(cache.resolve()) and Path(f["path"]).is_file()
                        and digest(Path(f["path"]).read_bytes()) == f["sha256"] for f in files)):
            return report
    cache.mkdir(parents=True, exist_ok=True)
    try:
        with snapshot(root, revision) as copy:
            netlist_path = cache / "netlist.xml"
            netlist = parse_netlist(export_netlist(copy, document, netlist_path))
            pages = resolve_pages(copy, document, netlist["pages"])
            if len(pages) > MAX_PAGES:
                raise PcbAiError("scene_too_large", "Too many schematic pages")
            clean, measured = copy / "pcbai-svg", copy / "pcbai-svg-cal"
            source = within(copy, document)
            command([find_kicad_cli(), "sch", "export", "svg", source, "--output", clean,
                     "--exclude-drawing-sheet", "--no-background-color"], copy)
            nonce = secrets.token_hex(8)
            expected = _calibrate(copy, nonce)
            command([find_kicad_cli(), "sch", "export", "svg", source, "--output", measured,
                     "--exclude-drawing-sheet", "--no-background-color"], copy)
            by_names = {p["names"]: p for p in pages}
            if len(by_names) != len(pages):
                raise PcbAiError("invalid_document", "Duplicate schematic sheet paths")
            records = {}
            outputs = sorted(p for p in measured.iterdir() if p.is_file() and p.suffix == ".svg")
            for calibrated in outputs:
                names, observed, box = _measure(calibrated, nonce)
                page = by_names.get(names)
                display = clean / calibrated.name
                if page is None or names in records or not display.is_file():
                    raise PcbAiError("invalid_transform", "SVG page does not match one netlist sheet")
                file = within(copy, page["document"])
                points, _ = expected[file]
                p, q, r = observed
                a, b = (q[0] - p[0]) / (points[1][0] - points[0][0]), (q[1] - p[1]) / (points[1][0] - points[0][0])
                c, d = (r[0] - p[0]) / (points[2][1] - points[0][1]), (r[1] - p[1]) / (points[2][1] - points[0][1])
                x, y = points[0]
                matrix = [a, b, c, d, p[0] - a * x - c * y, p[1] - b * x - d * y]
                _, clean_box = svg_metadata(display)
                if clean_box != box:
                    raise PcbAiError("invalid_transform", "Display and calibration SVG coordinate systems differ")
                target = cache / f"page-{len(records) + 1}.svg"
                shutil.copyfile(display, target)
                records[names] = dict(page, path=str(target), sha256=digest(target.read_bytes()), viewbox=box,
                                      mm_to_svg=matrix, svg_to_mm=inverse(matrix))
            if set(records) != set(by_names):
                raise PcbAiError("invalid_transform", "Some schematic pages produced no SVG")
            ordered = sorted(records.values(), key=lambda p: (_page_order(p["number"]), p["names"]))
            report = dict(document=document, revision=revision, pages=ordered, netlist=str(netlist_path),
                          netlist_sha256=digest(netlist_path.read_bytes()))
            manifest.write_text(json.dumps(report, allow_nan=False), encoding="utf-8")
            return report
    except Exception:
        if cache.resolve().is_relative_to(Path(destination).resolve()):
            shutil.rmtree(cache)
        raise


def _page_order(value):
    try:
        return (0, int(value), "")
    except (TypeError, ValueError):
        return (1, 0, str(value))
