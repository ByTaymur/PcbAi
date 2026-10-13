"""Independent route lengths, DRC identities and placement boundary measurements."""
import math
from collections import Counter

from pcbai.core.contract import PcbAiError
from pcbai.kicad.board import board
from pcbai.pcb.engine_guard import canonical_uuid
from pcbai.views import arc_points, graphic_points, scene_pcb, xy
from pcbai.verify.findings import comparison_id


def finding_key(finding):
    # Duplicate row suffixes may change as rows are added/removed; Counter keeps their multiplicity.
    return comparison_id(finding)


def active_errors(check):
    return Counter(finding_key(f) for f in check["findings"]
                   if f.get("severity") == "error" and not f.get("excluded", False))


def added_errors(before, after):
    remaining = active_errors(after) - active_errors(before)
    added = []
    for finding in after["findings"]:
        key = finding_key(finding)
        if finding.get("severity") == "error" and not finding.get("excluded", False) and remaining[key]:
            added.append(finding)
            remaining[key] -= 1
    return added


def unconnected(check):
    return sum(f.get("group") == "unconnected_items" and not f.get("excluded", False) for f in check["findings"])


def routing(data):
    root, per_layer = board(data), {}
    for node in root.children:
        if node.name not in {"segment", "arc"}:
            continue
        if node.name == "segment":
            length = math.dist(xy(node, "start"), xy(node, "end"))
        else:
            start, mid, end = xy(node, "start"), xy(node, "mid"), xy(node, "end")
            points = arc_points(start, mid, end)
            # Sampled circular path, with <=0.005 mm chord approximation from the view geometry reader.
            length = sum(math.dist(a, b) for a, b in zip(points, points[1:], strict=False))
        layer = node.child("layer")
        if layer is None:
            raise PcbAiError("invalid_geometry", "Track has no layer")
        per_layer[layer.value()] = per_layer.get(layer.value(), 0) + length
    return dict(via_count=len(root.all("via")), segment_count=len(root.all("segment")),
                arc_count=len(root.all("arc")), length_mm=round(sum(per_layer.values()), 6),
                layer_length_mm={k: round(v, 6) for k, v in per_layer.items()},
                arc_length_approximate=bool(root.all("arc")))


def outline_loops(data):
    fragments, loops = [], []
    for node in board(data).children:
        layer = node.child("layer") if node.atom is None else None
        if not layer or layer.value() != "Edge.Cuts" or not node.name.startswith("gr_"):
            continue
        points, closed = graphic_points(node)
        if not points:
            raise PcbAiError("invalid_outline", "Unsupported board outline geometry")
        if closed:
            loops.append(points)
        else:
            fragments.append(points)
    return join_loops(fragments, loops)


def join_loops(fragments, loops):
    """Connect fragment endpoints; storage order is not contour order in KiCad."""
    fragments, loops = [list(p) for p in fragments], [list(p) for p in loops]
    while fragments:
        points = fragments.pop()
        while math.dist(points[-1], points[0]) > 1e-5:
            match = next(((i, False) for i, p in enumerate(fragments) if math.dist(p[0], points[-1]) <= 1e-5), None)
            if match is None:
                match = next(((i, True) for i, p in enumerate(fragments) if math.dist(p[-1], points[-1]) <= 1e-5), None)
            if match is None:
                raise PcbAiError("invalid_outline", "Placement requires a closed board outline")
            index, reverse = match
            fragment = fragments.pop(index)
            points.extend((list(reversed(fragment)) if reverse else fragment)[1:])
        loops.append(points)
    if not loops:
        raise PcbAiError("invalid_outline", "Placement requires a board outline")
    return loops


def point_inside(point, loops):
    x, y = point
    inside = False
    for poly in loops:
        for a, b in zip(poly, [*poly[1:], poly[0]], strict=False):
            ax, ay = a
            bx, by = b
            cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
            if abs(cross) < 1e-6 and min(ax, bx) - 1e-6 <= x <= max(ax, bx) + 1e-6 and min(ay, by) - 1e-6 <= y <= max(ay, by) + 1e-6:
                return True
            if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
                inside = not inside
    return inside


def segment_inside(a, b, loops):
    """Partition at every outline intersection; each open interval must lie in board material."""
    if not point_inside(a, loops) or not point_inside(b, loops):
        return False
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 < 1e-16:
        return True
    cuts = {0.0, 1.0}
    for poly in loops:
        for c, d in zip(poly, [*poly[1:], poly[0]], strict=True):
            ex, ey = d[0] - c[0], d[1] - c[1]
            cx, cy = c[0] - a[0], c[1] - a[1]
            cross = dx * ey - dy * ex
            if abs(cross) < 1e-12:
                if abs(cx * dy - cy * dx) < 1e-9:
                    for p in (c, d):
                        t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2
                        if 0 < t < 1:
                            cuts.add(t)
                continue
            t, u = (cx * ey - cy * ex) / cross, (cx * dy - cy * dx) / cross
            if 0 < t < 1 and -1e-9 <= u <= 1 + 1e-9:
                cuts.add(t)
    cuts = sorted(cuts)
    return all(point_inside([a[0] + dx * (left + right) / 2, a[1] + dy * (left + right) / 2], loops)
               for left, right in zip(cuts, cuts[1:], strict=False) if right - left > 1e-9)


def outside_footprints(data, moved):
    if not moved:
        return []
    loops = outline_loops(data)
    selected = {canonical_uuid(m["uuid"]) for m in moved}
    outside = []
    for item in scene_pcb(data)["items"]:
        if item["type"] != "footprint" or canonical_uuid(item["uuid"]) not in selected:
            continue
        if item["courtyard"]:
            footprint_loops = join_loops([e["points"] for e in item["courtyard"] if not e["closed"]],
                                        [e["points"] for e in item["courtyard"] if e["closed"]])
        else:
            box = item["bbox"]
            footprint_loops = [[[box[0], box[1]], [box[0], box[3]], [box[2], box[3]], [box[2], box[1]]]]
        edges_inside = all(segment_inside(a, b, loops) for poly in footprint_loops
                           for a, b in zip(poly, [*poly[1:], poly[0]], strict=True))
        # A footprint can completely surround an internal cutout without intersecting its edges.
        encloses_cutout = any(point_inside([p[0] + dx, p[1] + dy], footprint_loops)
                              and not point_inside([p[0] + dx, p[1] + dy], loops)
                              for loop in loops for p in loop
                              for dx, dy in ((1e-4, 1e-4), (-1e-4, 1e-4), (1e-4, -1e-4), (-1e-4, -1e-4)))
        if not edges_inside or encloses_cutout:
            outside.append(dict(reference=item["reference"], uuid=item["uuid"], at=item["at"]))
    return outside
