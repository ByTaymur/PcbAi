"""Minimal byte-preserving PCB edits. Each planner returns new bytes; only the touched atoms change.

Footprint child geometry is stored in the footprint's local frame (unrotated); pad and text angles are
stored board-absolute. Rules below were measured against KiCad's own pcbnew Rotate/Flip (test oracle).
"""

import math

from pcbai.core.contract import PcbAiError
from pcbai.sexpr import Document
from pcbai.views import number

GRAPHICS = {"fp_line", "fp_arc", "fp_circle", "fp_rect", "fp_poly", "fp_curve"}
TEXTS = {"property", "fp_text", "fp_text_box"}
UNSUPPORTED = {"zone", "group", "dimension", "fp_image"}


def fmt(value):
    """KiCad-style number: at most 6 decimals, no trailing zeros, no negative zero."""
    text = f"{round(value, 6):.6f}".rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def angle(value):
    value = math.fmod(value, 360.0)
    if value <= -180:
        value += 360
    elif value > 180:
        value -= 360
    return round(value, 6)


def flip_layer(name):
    if name.startswith("F."):
        return "B." + name[2:]
    if name.startswith("B."):
        return "F." + name[2:]
    return name


class Edits:
    """Collected (start, end, text) replacements applied back to front."""

    def __init__(self, data):
        self.data = data
        self.doc = Document(data)
        self.changes = []

    def atom(self, node, text):
        if node.atom is None:
            raise PcbAiError("invalid_edit", "Only atoms can be replaced")
        self.changes.append((node.start, node.end, text.encode("utf-8")))

    def insert(self, offset, text):
        self.changes.append((offset, offset, text.encode("utf-8")))

    def result(self):
        data = self.data
        last = None
        for start, end, text in sorted(self.changes, key=lambda c: (c[0], c[1]), reverse=True):
            if last is not None and end > last:
                raise PcbAiError("invalid_edit", "Overlapping edits")
            data = data[:start] + text + data[end:]
            last = start
        Document(data)
        return data


def quoted(text):
    import json
    return json.dumps(text, ensure_ascii=False)


def footprint_by_reference(root, reference):
    from pcbai.sch.model import properties

    matches = []
    for fp in root.all("footprint"):
        props = properties(fp)
        ref = props.get("Reference") or next((t.value(2) for t in fp.all("fp_text") if t.value() == "reference"), None)
        if ref == reference:
            matches.append(fp)
    if not matches:
        raise PcbAiError("unknown_reference", f"Footprint {reference} not found")
    if len(matches) > 1:
        raise PcbAiError("ambiguous_reference", f"Footprint {reference} occurs more than once")
    return matches[0]


def _xy_nodes(node):
    """Every local (x y) coordinate node of one graphic/text/pad, including nested pts and pad primitives."""
    found = []
    for child in node.children:
        if child.atom is not None:
            continue
        if child.name in {"start", "end", "mid", "center", "at", "xy"}:
            found.append(child)
        elif child.name in {"pts", "primitives", "arc"} or child.name in GRAPHICS or child.name.startswith("gr_"):
            found.extend(_xy_nodes(child))
    return found


def plan_move(data, reference, x=None, y=None, rotation=None, side=None):
    """Move to absolute (x, y) mm, set absolute rotation (degrees), and/or set side ('front'/'back')."""
    edits = Edits(data)
    if edits.doc.root.name != "kicad_pcb":
        raise PcbAiError("invalid_document", "Expected a KiCad PCB")
    change = _move(edits, footprint_by_reference(edits.doc.root, reference), x, y, rotation, side)
    return dict(data=edits.result(), **change)


def plan_moves(data, operations, skip_unsupported=False):
    """Several footprint moves in one pass (one parse); each operation as in plan_move."""
    edits = Edits(data)
    if edits.doc.root.name != "kicad_pcb":
        raise PcbAiError("invalid_document", "Expected a KiCad PCB")
    changes, refused = [], []
    for op in operations:
        mark = len(edits.changes)
        try:
            changes.append(_move(edits, footprint_by_reference(edits.doc.root, op["reference"]), op.get("x"),
                                 op.get("y"), op.get("rotation"), op.get("side")))
        except PcbAiError as exc:
            if not skip_unsupported:
                raise
            del edits.changes[mark:]
            refused.append((op["reference"], exc.code))
    return dict(data=edits.result(), changes=changes, refused=refused)


def _move(edits, fp, x, y, rotation, side):
    for child in fp.children:
        if child.atom is None and child.name in UNSUPPORTED:
            raise PcbAiError("unsupported_edit", f"Footprint contains {child.name}; edit it in KiCad")
    at = fp.child("at")
    layer_node = fp.child("layer")
    if at is None or layer_node is None:
        raise PcbAiError("invalid_document", "Footprint has no position or layer")
    old = [number(at.value()), number(at.value(2))]
    old_angle = number(at.value(3, "0"))
    current_side = "back" if layer_node.value().startswith("B.") else "front"
    flip = side is not None and side != current_side
    # Order: flip left-right about the footprint position (θ → 180° − θ, local y → −y, absolute pad/text
    # angles a → 180° − a), then rotate everything by the delta to the requested absolute rotation.
    flipped_angle = angle(180 - old_angle) if flip else old_angle
    new_angle = flipped_angle if rotation is None else angle(rotation)
    delta = new_angle - flipped_angle
    new = [old[0] if x is None else number(x), old[1] if y is None else number(y)]
    if abs(new[0]) > 1e5 or abs(new[1]) > 1e5:
        raise PcbAiError("invalid_arguments", "Position is outside the board coordinate range")
    position = f"{fmt(new[0])} {fmt(new[1])}"
    if len(at.children) >= 4:
        edits.changes.append((at.children[1].start, at.children[3].end, f"{position} {fmt(new_angle)}".encode()))
    else:
        edits.changes.append((at.children[1].start, at.children[2].end,
                              (position + (f" {fmt(new_angle)}" if new_angle else "")).encode()))
    for child in fp.children:
        if child.atom is not None:
            continue
        name = child.name
        if name == "pad" or name in TEXTS:
            node = child.child("at")
            if node is not None:
                a = number(node.value(3, "0"))
                a = angle((180 - a if flip else a) + delta)
                if flip:
                    edits.atom(node.children[2], fmt(-number(node.value(2))))
                if len(node.children) >= 4:
                    edits.atom(node.children[3], fmt(a))
                elif a:
                    edits.insert(node.children[2].end, " " + fmt(a))
        if not flip:
            continue
        if name in GRAPHICS or name in {"pad", "fp_text_box"}:
            for node in _xy_nodes(child):
                if name == "pad" and node.name == "at" and any(p is node for p in child.children):
                    continue  # pad position handled above
                edits.atom(node.children[2], fmt(-number(node.value(2))))
        for node in [child.child("layer"), child.child("layers")]:
            if node is None:
                continue
            for atom in node.children[1:]:
                if atom.atom is not None and flip_layer(atom.atom) != atom.atom:
                    edits.atom(atom, quoted(flip_layer(atom.atom)))
        if name in TEXTS:
            _toggle_mirror(edits, child)
    if flip:
        edits.atom(layer_node.children[1], quoted(flip_layer(layer_node.value())))
    return dict(before=dict(at=old, rotation=old_angle, side=current_side),
                after=dict(at=new, rotation=new_angle, side=side or current_side))


def _toggle_mirror(edits, text):
    effects = text.child("effects")
    if effects is None:
        return
    justify = effects.child("justify")
    if justify is None:
        edits.insert(effects.end - 1, " (justify mirror)")
        return
    mirror = next((a for a in justify.children[1:] if a.atom == "mirror"), None)
    if mirror is None:
        edits.insert(justify.end - 1, " mirror")
    else:
        # Remove the atom and the whitespace before it.
        start = mirror.start
        while start > 0 and edits.data[start - 1:start] in {b" ", b"\t"}:
            start -= 1
        edits.changes.append((start, mirror.end, b""))


def net_names(root):
    """Net names of a board in either format: KiCad ≤9 (net N "name") table or KiCad 10 (net "name")."""
    table = {n.value(): n.value(2) for n in root.all("net") if n.value(2) is not None}
    names = set(table.values())

    def visit(node):
        for child in node.children:
            if child.atom is None:
                if child.name == "net" and child.value() is not None:
                    names.add(child.value(2) or table.get(child.value(), child.value()))
                else:
                    visit(child)
    visit(root)
    names.discard("")
    return table, names


def node_net(node, table):
    net = node.child("net")
    if net is None:
        return None
    return net.value(2) or table.get(net.value(), net.value())


def plan_track_width(data, width, uuids=None, net=None):
    """Set the width of the listed track UUIDs or of every track on one net."""
    width = number(width)
    if not 0.01 <= width <= 10:
        raise PcbAiError("invalid_arguments", "Track width must be 0.01–10 mm")
    if bool(uuids) == bool(net):
        raise PcbAiError("invalid_arguments", "Give either track UUIDs or one net name")
    edits = Edits(data)
    root = edits.doc.root
    if root.name != "kicad_pcb":
        raise PcbAiError("invalid_document", "Expected a KiCad PCB")
    table, names = net_names(root)
    if net and net not in names:
        raise PcbAiError("unknown_net", f"Net {net} is not on this board")
    wanted = set(uuids or [])
    selected, old = [], set()
    for node in root.all("segment") + root.all("arc"):
        uuid = node.child("uuid").value() if node.child("uuid") else None
        if (uuid in wanted) if uuids else node_net(node, table) == net:
            w = node.child("width")
            if w is None:
                raise PcbAiError("invalid_document", "Track without width")
            old.add(number(w.value()))
            edits.atom(w.children[1], fmt(width))
            selected.append(uuid)
    if uuids and set(selected) != wanted:
        raise PcbAiError("unknown_item", "Some track UUIDs are not on this board")
    if not selected:
        raise PcbAiError("unknown_item", "No tracks matched")
    return dict(data=edits.result(), tracks=selected, old_widths=sorted(old), width=width)


def plan_zone(data, net, layer, points, clearance=0.5, min_thickness=0.25, priority=0):
    """Append a copper zone outline. KiCad fills it (DRC --refill-zones) in the copy before apply."""
    import secrets

    root = Document(data).root
    if root.name != "kicad_pcb":
        raise PcbAiError("invalid_document", "Expected a KiCad PCB")
    table, names = net_names(root)
    if net not in names:
        raise PcbAiError("unknown_net", f"Net {net} is not on this board")
    layers = root.child("layers")
    copper = {n.value() for n in layers.children[1:] if n.atom is None and (n.value() or "").endswith(".Cu")} \
        if layers else set()
    if layer not in copper:
        raise PcbAiError("invalid_arguments", "Zone layer must be an enabled copper layer")
    if not 3 <= len(points) <= 256:
        raise PcbAiError("invalid_arguments", "Zone outline needs 3–256 points")
    pts = [[number(x), number(y)] for x, y in points]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1], strict=True)) / 2
    if abs(area) < 0.01:
        raise PcbAiError("invalid_arguments", "Zone outline has no area")
    for value, low, high in ((clearance, 0, 10), (min_thickness, 0.01, 10)):
        if not low <= number(value) <= high:
            raise PcbAiError("invalid_arguments", "Zone clearance/thickness out of range")
    numbered = next((k for k, v in table.items() if v == net), None)
    net_text = f'(net {numbered}) (net_name {quoted(net)})' if table and numbered is not None else f"(net {quoted(net)})"
    uuid = "-".join([secrets.token_hex(4), secrets.token_hex(2), "4" + secrets.token_hex(2)[1:],
                     "8" + secrets.token_hex(2)[1:], secrets.token_hex(6)])
    xy = " ".join(f"(xy {fmt(x)} {fmt(y)})" for x, y in pts)
    zone = (f'\t(zone {net_text} (layer {quoted(layer)}) (uuid "{uuid}") (priority {int(priority)}) '
            f"(hatch edge 0.5) (connect_pads (clearance {fmt(number(clearance))})) "
            f"(min_thickness {fmt(number(min_thickness))}) (filled_areas_thickness no) "
            f"(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5)) "
            f"(polygon (pts {xy})))\n")
    end = root.end - 1
    changed = data[:end] + zone.encode() + data[end:]
    Document(changed)
    return dict(data=changed, uuid=uuid, area_mm2=abs(area), net=net, layer=layer)


def splice_fill(candidate, filled_board, uuid):
    """Copy KiCad's computed filled_polygon nodes of the new zone (by UUID) into the candidate.

    The zone node itself stays in the file's own format (KiCad saves its copy in the newest format, whose
    net syntax an older file would misread); filled_polygon syntax is the same in both.
    """
    source = Document(filled_board).root
    zone = next((z for z in source.all("zone") if z.child("uuid") and z.child("uuid").value() == uuid), None)
    if zone is None:
        raise PcbAiError("invalid_report", "KiCad did not keep the new zone while filling")
    fills = [filled_board[n.start:n.end] for n in zone.all("filled_polygon")]
    if not fills:
        return candidate, 0
    doc = Document(candidate)
    target = next(z for z in doc.root.all("zone") if z.child("uuid") and z.child("uuid").value() == uuid)
    insert = target.end - 1
    changed = candidate[:insert] + b" " + b" ".join(fills) + candidate[insert:]
    Document(changed)
    return changed, len(fills)
