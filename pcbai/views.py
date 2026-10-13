"""Saved PCB geometry in KiCad millimetres. File text is data, never executable."""

import math

from pcbai.core.contract import PcbAiError
from pcbai.kicad.board import board
from pcbai.kicad.files import digest
from pcbai.sch.model import properties


def number(value):
    try:
        n = float(value)
        if not math.isfinite(n) or abs(n) > 1e6:
            raise ValueError()
        return n
    except (ValueError, TypeError) as exc:
        raise PcbAiError("invalid_geometry", "Invalid or nonfinite geometry") from exc


def xy(node, name="at"):
    child = node.child(name)
    if child is None:
        raise PcbAiError("invalid_geometry", f"Missing {name}")
    return [number(child.value()), number(child.value(2))]


def angle(node):
    at = node.child("at")
    return number(at.value(3, "0")) if at else 0


def rotate(point, degrees):
    a = math.radians(degrees)
    x, y = point
    return [x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)]


def transform(point, origin, degrees):
    p = rotate(point, degrees)
    return [p[0] + origin[0], p[1] + origin[1]]


def bbox(points, padding=0):
    return [
        min(p[0] for p in points) - padding,
        min(p[1] for p in points) - padding,
        max(p[0] for p in points) + padding,
        max(p[1] for p in points) + padding,
    ]


def arc_points(start, mid, end):
    x1, y1 = start
    x2, y2 = mid
    x3, y3 = end
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-10:
        return [start, mid, end]
    u1, u2, u3 = x1 * x1 + y1 * y1, x2 * x2 + y2 * y2, x3 * x3 + y3 * y3
    cx = (u1 * (y2 - y3) + u2 * (y3 - y1) + u3 * (y1 - y2)) / d
    cy = (u1 * (x3 - x2) + u2 * (x1 - x3) + u3 * (x2 - x1)) / d
    angles = [math.atan2(y - cy, x - cx) for x, y in [start, mid, end]]
    sweep = (angles[2] - angles[0]) % math.tau
    if (angles[1] - angles[0]) % math.tau > sweep:
        sweep -= math.tau
    radius = math.hypot(x1 - cx, y1 - cy)
    # Chord approximation <= 0.005 mm, capped to keep hostile geometry bounded.
    steps = min(4096, max(8, math.ceil(abs(sweep) * math.sqrt(max(radius, 1) / 0.04))))
    return [
        [
            cx + radius * math.cos(angles[0] + sweep * i / steps),
            cy + radius * math.sin(angles[0] + sweep * i / steps),
        ]
        for i in range(steps + 1)
    ]


def graphic_points(node):
    shape = node.name.split("_", 1)[-1]
    if shape == "line":
        return [xy(node, "start"), xy(node, "end")], False
    if shape == "arc":
        return arc_points(xy(node, "start"), xy(node, "mid"), xy(node, "end")), False
    if shape == "rect":
        a, b = xy(node, "start"), xy(node, "end")
        return [a, [b[0], a[1]], b, [a[0], b[1]]], True
    if shape == "circle":
        c, e = xy(node, "center"), xy(node, "end")
        r = math.dist(c, e)
        count = min(4096, max(32, math.ceil(math.tau * math.sqrt(max(r, 1) / 0.04))))
        return [
            [c[0] + r * math.cos(math.tau * i / count), c[1] + r * math.sin(math.tau * i / count)]
            for i in range(count)
        ], True
    if shape == "poly":
        pts = node.child("pts")
        return [[number(p.value()), number(p.value(2))] for p in pts.all("xy")] if pts else [], True
    return [], False


def scene_pcb(data):
    root = board(data)
    items, warnings = [], set()
    layers_node = root.child("layers")
    layers = [n.value() for n in layers_node.children[1:]] if layers_node else []

    def identity(node):
        uuid = node.child("uuid") or node.child("tstamp")
        return uuid.value() if uuid else "anonymous-" + digest(data[node.start : node.end])[:24]

    definitions = {n.value(): n.value(2) for n in root.all("net")}  # built once: was quadratic (G5)

    def common(node, kind, layer=None):
        layer_node = node.child("layer")
        net_node = node.child("net")
        net_name = None
        if net_node:
            # KiCad ≤9: (net N "name") or (net N) + top-level table; KiCad 10: (net "name").
            net_name = net_node.value(2) or definitions.get(net_node.value(), net_node.value())
        return dict(
            type=kind,
            uuid=identity(node),
            layer=layer or (layer_node.value() if layer_node else None),
            net=net_name,
            trusted=False,
        )

    for fp in root.all("footprint"):
        origin, degrees = xy(fp), angle(fp)
        layer = fp.child("layer").value() if fp.child("layer") else "F.Cu"
        # KiCad serializes back-side local geometry already flipped. Mirroring it again is incorrect.
        props = properties(fp)
        reference = props.get("Reference") or next(
            (n.value(2) for n in fp.all("fp_text") if n.value() == "reference"), "?"
        )
        outline, fallback, pads = [], [], []
        for n in fp.children:
            if n.name and n.name.startswith("fp_"):
                points, closed = graphic_points(n)
                points = [transform(p, origin, degrees) for p in points]
                fallback.extend(points)
                ln = n.child("layer")
                if ln and ln.value() in {"F.CrtYd", "B.CrtYd"} and points:
                    outline.append(dict(points=points, closed=closed))
        for pad in fp.all("pad"):
            at = transform(xy(pad), origin, degrees)
            size = xy(pad, "size")
            if min(size) <= 0:
                raise PcbAiError("invalid_geometry", "Pad size must be positive")
            rotation = angle(pad)  # serialized pad rotation is board-absolute
            corners = [
                transform([x * size[0] / 2, y * size[1] / 2], at, rotation)
                for x, y in [(-1, -1), (1, -1), (1, 1), (-1, 1)]
            ]
            p = common(pad, "pad", layer)
            pad_layers = pad.child("layers")
            p.update(
                at=at,
                size=size,
                rotation=rotation,
                shape=pad.value(3),
                number=pad.value(),
                reference=reference,
                parent=identity(fp),
                polygon=corners,
                bbox=bbox(corners),
                layers=[n.atom for n in pad_layers.children[1:]] if pad_layers else [layer],
            )
            ratio = pad.child("roundrect_rratio")
            p["roundrect_ratio"] = number(ratio.value()) if ratio else .25
            if not 0 <= p["roundrect_ratio"] <= .5:
                raise PcbAiError("invalid_geometry", "Invalid rounded pad corner ratio")
            pads.append(p)
            fallback.extend(corners)
            if p["shape"] not in {"circle", "rect", "oval", "roundrect"}:
                warnings.add(p["shape"] + " pad hit geometry uses its bounding rectangle")
        points = [p for line in outline for p in line["points"]] or fallback or [origin]
        item = common(fp, "footprint", layer)
        item.update(
            at=origin,
            rotation=degrees,
            reference=reference,
            value=props.get("Value", ""),
            footprint=fp.value(),
            side="back" if layer.startswith("B.") else "front",
            bbox=bbox(points, 0.2),
            courtyard=outline,
        )
        items.append(item)
        items.extend(pads)
    for name in ["segment", "arc"]:
        for node in root.all(name):
            points = (
                [xy(node, "start"), xy(node, "end")]
                if name == "segment"
                else arc_points(xy(node, "start"), xy(node, "mid"), xy(node, "end"))
            )
            width = number(node.child("width").value())
            item = common(node, "track")
            item.update(points=points, width=width, at=points[0], bbox=bbox(points, width / 2))
            items.append(item)
    for node in root.all("via"):
        at, size = xy(node), number(node.child("size").value())
        item = common(node, "via")
        ln = node.child("layers")
        item.update(
            at=at,
            size=[size, size],
            bbox=bbox([at], size / 2),
            layers=[n.atom for n in ln.children[1:]] if ln else ["*.Cu"],
        )
        items.append(item)
    for node in root.all("zone"):
        polygons = []
        for polygon in node.all("filled_polygon") or node.all("polygon"):
            pts = polygon.child("pts")
            points = [[number(p.value()), number(p.value(2))] for p in pts.all("xy")] if pts else []
            if points:
                ln = polygon.child("layer")
                polygons.append(dict(points=points, layer=ln.value() if ln else None))
        points = [p for poly in polygons for p in poly["points"]]
        if points:
            item = common(node, "zone")
            ln = node.child("layers")
            item.update(
                polygons=polygons,
                at=points[0],
                bbox=bbox(points),
                layers=[n.atom for n in ln.children[1:]] if ln else [item["layer"]],
            )
            items.append(item)
    for node in root.children:
        ln = node.child("layer")
        if ln and ln.value() == "Edge.Cuts" and node.name and node.name.startswith("gr_"):
            points, closed = graphic_points(node)
            if points:
                item = common(node, "edge")
                item.update(
                    points=points + ([points[0]] if closed else []),
                    width=0.1,
                    at=points[0],
                    bbox=bbox(points),
                )
                items.append(item)
            else:
                warnings.add("Unsupported outline primitive: " + node.name)
    edges = [p for i in items if i["type"] == "edge" for p in i["points"]]
    extents = edges or [p for i in items for p in [i["bbox"][:2], i["bbox"][2:]]]
    if not extents:
        raise PcbAiError("empty_scene", "PCB has no supported geometry")
    if len(items) > 200000:
        raise PcbAiError("scene_too_large", "Scene exceeds the item limit")
    return dict(
        space="pcb", units="mm", layers=layers, bbox=bbox(extents), items=items, warnings=sorted(warnings)
    )


def inside(point, polygon):
    x, y = point
    hit = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            hit = not hit
    return hit


def line_distance(point, points):
    best = math.inf
    for a, b in zip(points, points[1:], strict=False):
        dx, dy = b[0] - a[0], b[1] - a[1]
        denominator = dx * dx + dy * dy
        t = (
            max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / denominator))
            if denominator
            else 0
        )
        best = min(best, math.dist(point, [a[0] + t * dx, a[1] + t * dy]))
    return best


def visible(item, layers):
    if layers is None:
        return True
    own = item.get("layers", [item["layer"]])
    return any(
        layer in own
        or ("*.Cu" in own and layer.endswith(".Cu"))
        or ("F&B.Cu" in own and layer in {"F.Cu", "B.Cu"})
        for layer in layers
    )


def hit_test(scene, x, y, layers=None, tolerance=0.5):
    point = [number(x), number(y)]
    hits = []
    for item in scene["items"]:
        if not visible(item, layers):
            continue
        box = item["bbox"]
        if not (
            box[0] - tolerance <= x <= box[2] + tolerance and box[1] - tolerance <= y <= box[3] + tolerance
        ):
            continue
        kind = item["type"]
        if kind in {"track", "edge"}:
            distance = max(0, line_distance(point, item["points"]) - item["width"] / 2)
        elif kind == "zone":
            distance = (
                0
                if any(
                    inside(point, p["points"])
                    for p in item["polygons"]
                    if layers is None or (p["layer"] or item["layer"]) in layers
                )
                else math.inf
            )
        elif kind == "via" or (kind == "pad" and item["shape"] == "circle"):
            distance = max(0, math.dist(point, item["at"]) - item["size"][0] / 2)
        elif kind == "pad" and item["shape"] in {"oval", "roundrect"}:
            local = rotate([point[0]-item["at"][0], point[1]-item["at"][1]], -item["rotation"])
            w, h = item["size"]
            r = min(w, h) * (.5 if item["shape"] == "oval" else item["roundrect_ratio"])
            qx, qy = abs(local[0])-w/2+r, abs(local[1])-h/2+r
            distance = max(0, math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r)
        elif kind == "pad":
            distance = (
                0
                if inside(point, item["polygon"])
                else line_distance(point, item["polygon"] + [item["polygon"][0]])
            )
        else:
            distance = math.hypot(max(box[0] - x, 0, x - box[2]), max(box[1] - y, 0, y - box[3]))
        if distance <= tolerance:
            hits.append(dict(item, distance_mm=distance))
    priorities = {"pad": 0, "via": 1, "track": 2, "footprint": 3, "edge": 4, "zone": 5}
    return sorted(
        hits,
        key=lambda i: (
            i["distance_mm"],
            -1 if i["type"] == "footprint" and math.dist(point, i["at"]) <= 0.2 else priorities[i["type"]],
        ),
    )[:20]
