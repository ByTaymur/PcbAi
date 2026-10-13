"""Compare footprint children of two boards by UUID in absolute board coordinates (oracle checks)."""
import math

from pcbai.pcb.edit import GRAPHICS, TEXTS, _xy_nodes, angle
from pcbai.sexpr import Document
from pcbai.views import number, transform


def describe(data):
    out = {}
    for fp in Document(data).root.all("footprint"):
        at = fp.child("at")
        origin, rot = [number(at.value()), number(at.value(2))], number(at.value(3, "0"))
        fid = fp.child("uuid").value()
        out[fid] = dict(kind="footprint", at=origin, angle=angle(rot), layer=fp.child("layer").value())
        for child in fp.children:
            if child.atom is not None or child.child("uuid") is None:
                continue
            name = child.name
            if name not in GRAPHICS and name not in TEXTS and name != "pad":
                continue
            entry = dict(kind=name)
            points = []
            for node in _xy_nodes(child):
                if name == "pad" and node.name != "at" and any(p is node for p in child.children):
                    continue
                if name == "pad" and node.name == "at" and not any(p is node for p in child.children):
                    continue
                points.append(transform([number(node.value()), number(node.value(2))], origin, rot))
            if name == "fp_rect":
                # KiCad saves a rectangle rotated off-axis as a 4-point fp_poly: compare the corners.
                (x0, y0), (x1, y1) = ([number(child.child(k).value()), number(child.child(k).value(2))]
                                      for k in ("start", "end"))
                points = [transform(p, origin, rot) for p in ([x0, y0], [x1, y0], [x1, y1], [x0, y1])]
                name = entry["kind"] = "fp_poly"
            if name == "pad" or name in TEXTS:
                own = child.child("at")
                if own is not None:
                    entry["angle"] = angle(number(own.value(3, "0")))
                    points = [transform([number(own.value()), number(own.value(2))], origin, rot)] + (
                        points if name != "pad" else [])
            entry["points"] = sorted((round(p[0], 3), round(p[1], 3)) for p in points)
            layers = [n.value() for n in [child.child("layer")] if n is not None]
            if child.child("layers"):
                layers += [a.atom for a in child.child("layers").children[1:] if a.atom]
            entry["layers"] = sorted(layers)
            effects = child.child("effects")
            justify = effects.child("justify") if effects is not None else None
            entry["mirror"] = bool(justify and any(a.atom == "mirror" for a in justify.children[1:]))
            out[child.child("uuid").value()] = entry
    return out


def differences(ours, oracle, angle_tolerance=0.01):
    a, b = describe(ours), describe(oracle)
    problems = []
    for key, expected in b.items():
        got = a.get(key)
        if got is None:
            problems.append((key, expected["kind"], "missing"))
            continue
        for field in ("layer", "layers", "mirror"):
            if field in expected and got.get(field) != expected[field]:
                problems.append((key, expected["kind"], field, got.get(field), expected[field]))
        if "angle" in expected:
            diff = abs(angle(got.get("angle", 0) - expected["angle"]))
            if expected["kind"] in TEXTS:
                # KiCad keeps footprint text upright on flip; angles 180° apart render identically.
                diff = min(diff, abs(180 - diff))
            if diff > angle_tolerance:
                problems.append((key, expected["kind"], "angle", got.get("angle"), expected["angle"]))
        if "at" in expected and math.dist(got["at"], expected["at"]) > 1e-3:
            problems.append((key, "footprint", "at", got["at"], expected["at"]))
        if "points" in expected:
            if len(got["points"]) != len(expected["points"]) or any(
                    math.dist(p, q) > 2e-3 for p, q in zip(got["points"], expected["points"], strict=False)):
                problems.append((key, expected["kind"], "points", got["points"][:3], expected["points"][:3]))
    return problems
