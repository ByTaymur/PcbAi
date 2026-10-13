"""Revision-bound KiCad SVGs with an independently measured mm-to-SVG transform."""

import json
import math
import re
import secrets
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli
from pcbai.kicad.cli import snapshot
from pcbai.kicad.exports import command
from pcbai.kicad.files import digest, within
from pcbai.sexpr import Document
from pcbai.views import number, scene_pcb


def svg_metadata(path):
    data = Path(path).read_bytes()
    if len(data) > 32 * 1024 * 1024 or b"<!ENTITY" in data.upper():
        raise PcbAiError("unsafe_svg", "SVG exceeds limits or contains entities")
    try:
        root = ET.fromstring(data)
        allowed = {
            "svg",
            "g",
            "path",
            "circle",
            "rect",
            "line",
            "polyline",
            "polygon",
            "ellipse",
            "text",
            "tspan",
            "title",
            "desc",
            "defs",
            "clipPath",
        }
        for node in root.iter():
            if node.tag.split("}")[-1] not in allowed:
                raise ValueError("Unsupported SVG element")
            for key, value in node.attrib.items():
                if (
                    key.split("}")[-1].lower().startswith("on")
                    or "href" in key.lower()
                    or "url(" in value.lower()
                ):
                    raise ValueError("Active or external SVG content")
        box = [number(v) for v in root.attrib["viewBox"].split()]
        if len(box) != 4 or min(box[2:]) <= 0:
            raise ValueError("Invalid viewBox")
        return root, box
    except (ET.ParseError, KeyError, ValueError) as exc:
        raise PcbAiError("unsafe_svg", "KiCad output is not a safe SVG") from exc


def apply_matrix(matrix, point):
    a, b, c, d, e, f = matrix
    x, y = point
    return [a * x + c * y + e, b * x + d * y + f]


def inverse(matrix):
    a, b, c, d, e, f = matrix
    det = a * d - b * c
    if not math.isfinite(det) or abs(det) < 1e-12:
        raise PcbAiError("invalid_transform", "Singular SVG transform")
    return [d / det, -b / det, -c / det, a / det, (c * f - d * e) / det, (b * e - a * f) / det]



SVG_OPTIONS = ["--page-size-mode", "2", "--exclude-drawing-sheet"]
# Layers that may carry the hidden calibration circles when they are not displayed.
CALIBRATION_LAYERS = ["Cmts.User", "Dwgs.User", "Eco1.User", "Eco2.User"]


def _calibration_points(bounds):
    x0, y0, x1, y1 = bounds
    width, height = x1 - x0, y1 - y0
    if min(width, height) < 0.1:
        raise PcbAiError("invalid_geometry", "Board is too small for SVG calibration")
    points = [
        [x0 + width * 0.25, y0 + height * 0.25],
        [x0 + width * 0.75, y0 + height * 0.25],
        [x0 + width * 0.25, y0 + height * 0.75],
    ]
    radii = [min(width, height) * v for v in [0.001234, 0.002345, 0.003456]]
    return points, radii, width, height


def _inject(source, bounds, layer):
    """Add three circles of distinct radii on ``layer`` of the copy; returns the original bytes."""
    original = source.read_bytes()
    parsed = Document(original)
    points, radii, _, _ = _calibration_points(bounds)
    additions = [
        f"(gr_circle (center {x:.7f} {y:.7f}) (end {x + r:.7f} {y:.7f}) "
        f'(stroke (width 0.01) (type solid)) (fill none) (layer "{layer}") (uuid "{secrets.token_hex(16)}"))'
        for (x, y), r in zip(points, radii, strict=True)
    ]
    source.write_bytes(
        original[: parsed.root.end - 1] + "\n".join(additions).encode() + original[parsed.root.end - 1 :]
    )
    return original


def _measure(path, bounds):
    """Solve the affine mm→SVG matrix from the three calibration circles of one plotted SVG."""
    points, radii, width, height = _calibration_points(bounds)
    root, box = svg_metadata(path)
    parents = {child: node for node in root.iter() for child in node}
    circles = [n for n in root.iter() if n.tag.split("}")[-1] == "circle"]
    observed = []
    for radius in radii:
        matches = [c for c in circles if abs(number(c.get("r")) - radius) <= 0.00011]
        if len(matches) != 1:
            raise PcbAiError("invalid_transform", "SVG calibration circles are ambiguous or absent")
        # KiCad emits these circles inside identity groups; other content (rotated text) may transform.
        node = matches[0]
        while node is not None:
            transform = node.get("transform")
            if transform and re.sub(r"\s+", "", transform) not in {"translate(00)scale(11)",
                                                                    "translate(0,0)scale(1,1)"}:
                raise PcbAiError("invalid_transform", "Unsupported KiCad SVG group transform")
            node = parents.get(node)
        observed.append([number(matches[0].get("cx")), number(matches[0].get("cy"))])
    p, q, r = observed
    a, b = (q[0] - p[0]) / (width * 0.5), (q[1] - p[1]) / (width * 0.5)
    c, d = (r[0] - p[0]) / (height * 0.5), (r[1] - p[1]) / (height * 0.5)
    x, y = points[0]
    matrix = [a, b, c, d, p[0] - a * x - c * y, p[1] - b * x - d * y]
    return dict(
        mm_to_svg=matrix,
        svg_to_mm=inverse(matrix),
        viewbox=box,
        calibration=dict(source_points=points, svg_points=observed),
    )


def calibrate(copy, document, destination, bounds):
    source = within(copy, document)
    original = _inject(source, bounds, "Edge.Cuts")
    try:
        command([find_kicad_cli(), "pcb", "export", "svg", source, "--output", destination,
                 "--layers", "Edge.Cuts", "--mode-single", *SVG_OPTIONS], copy)
        return _measure(destination, bounds)
    finally:
        source.write_bytes(original)
        Path(destination).unlink(missing_ok=True)


def plotted_names(data):
    """KiCad --mode-multi file suffix per canonical layer: user layer name (else canonical), '.' → '_'."""
    node = Document(data).root.child("layers")
    names = {}
    for entry in node.children[1:] if node else []:
        if entry.atom is None and entry.value():
            names[entry.value()] = (entry.value(3) or entry.value()).replace(".", "_")
    return names


def _render_multi(copy, document, cache, layers, available, bounds):
    """One KiCad call plots every display layer plus a hidden calibration layer; None selects the slow path.

    Output files are identified by KiCad's naming rule, and only when the produced set matches it exactly.
    """
    spare = next((n for n in CALIBRATION_LAYERS if n in available and n not in layers), None)
    source = within(copy, document)
    names = plotted_names(source.read_bytes())
    if spare is None or any(n not in names for n in [*layers, spare]):
        return None
    expected = {n: f"{source.stem}-{names[n]}.svg" for n in [*layers, spare]}
    if len(set(expected.values())) != len(expected):
        return None
    original = _inject(source, bounds, spare)
    output = copy / "pcbai-svg-multi"
    try:
        command([find_kicad_cli(), "pcb", "export", "svg", source, "--output", output,
                 "--layers", ",".join([*layers, spare]), "--mode-multi", *SVG_OPTIONS], copy)
    finally:
        source.write_bytes(original)
    produced = {p.name for p in output.iterdir() if p.is_file()} if output.is_dir() else set()
    if produced != set(expected.values()):
        return None
    mapping = _measure(output / expected[spare], bounds)
    records = []
    for index, layer in enumerate(layers):
        plotted = output / expected[layer]
        _, box = svg_metadata(plotted)
        if box != mapping["viewbox"]:
            raise PcbAiError("invalid_transform", "Layer SVG coordinate systems disagree")
        target = cache / f"layer-{index}.svg"
        shutil.copyfile(plotted, target)
        records.append(dict(name=layer, path=str(target), sha256=digest(target.read_bytes())))
    return mapping, records


def _render_each(copy, document, cache, layers, bounds):
    mapping = calibrate(copy, document, cache / "calibration.svg", bounds)
    records = []
    for index, layer in enumerate(layers):
        output = cache / f"layer-{index}.svg"
        command([find_kicad_cli(), "pcb", "export", "svg", within(copy, document), "--output", output,
                 "--layers", layer, "--mode-single", *SVG_OPTIONS], copy)
        _, box = svg_metadata(output)
        if box != mapping["viewbox"]:
            raise PcbAiError("invalid_transform", "Layer SVG coordinate systems disagree")
        records.append(dict(name=layer, path=str(output), sha256=digest(output.read_bytes())))
    return mapping, records


def render_pcb(root, document, revision, destination, layers=None, scene=None):
    """Caller serializes this cache and validates source revision before/after."""
    scene = scene or scene_pcb(within(root, document).read_bytes())
    available = scene["layers"]
    layers = (
        layers
        if layers is not None
        else list(reversed([n for n in available if n.endswith(".Cu")]))
        + [n for n in ["B.SilkS", "F.SilkS", "F.Fab", "B.Fab", "Edge.Cuts"] if n in available]
    )
    if (
        not layers
        or len(layers) > 64
        or len(set(layers)) != len(layers)
        or any(n not in available for n in layers)
    ):
        raise PcbAiError("invalid_arguments", "Select unique enabled PCB layers")
    cache = Path(destination) / digest(json.dumps([document, layers]).encode())[:24]
    manifest = cache / "manifest.json"
    if manifest.is_file():
        report = json.loads(manifest.read_text(encoding="utf-8"))
        if (
            report.get("document") == document
            and report.get("revision") == revision
            and [n["name"] for n in report["layers"]] == layers
            and all(
                Path(n["path"]).resolve().is_relative_to(cache.resolve())
                and Path(n["path"]).is_file()
                and digest(Path(n["path"]).read_bytes()) == n["sha256"]
                for n in report["layers"]
            )
        ):
            return report
    cache.mkdir(parents=True, exist_ok=True)
    try:
        with snapshot(root, revision) as copy:
            fast = _render_multi(copy, document, cache, layers, available, scene["bbox"])
            mode = "multi" if fast else "per-layer"
            mapping, records = fast or _render_each(copy, document, cache, layers, scene["bbox"])
            report = dict(document=document, revision=revision, bbox=scene["bbox"], layers=records,
                          plot_mode=mode, **mapping)
            manifest.write_text(json.dumps(report, allow_nan=False), encoding="utf-8")
            return report
    except Exception:
        # Only this newly owned cache under the private views root is removed.
        if cache.resolve().is_relative_to(Path(destination).resolve()):
            shutil.rmtree(cache)
        raise
