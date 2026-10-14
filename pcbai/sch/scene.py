"""Saved schematic page geometry in sheet millimetres. Net names come only from KiCad's netlist."""

import math
import re
import xml.etree.ElementTree as ET

from pcbai.core.contract import PcbAiError
from pcbai.sch.model import _schematic, canonical_path, properties
from pcbai.views import arc_points, bbox, number

UNIT = re.compile(r"_(\d+)_(\d+)$")
LABELS = ("label", "global_label", "hierarchical_label", "directive_label", "netclass_flag")


def point(node, name="at"):
    child = node.child(name)
    if child is None:
        raise PcbAiError("invalid_geometry", f"Missing {name}")
    return [number(child.value()), number(child.value(2))]


def orient(local, rotation, mirror):
    """Library (y up) → sheet offset (y down): KiCad applies the rotation, then the mirror."""
    x, y = local[0], -local[1]
    a = math.radians(rotation)
    c, s = round(math.cos(a), 12), round(math.sin(a), 12)
    x, y = x * c + y * s, -x * s + y * c
    if mirror == "x":
        y = -y
    elif mirror == "y":
        x = -x
    return [x, y]


def place(local, at, rotation, mirror):
    x, y = orient(local, rotation, mirror)
    return [round(at[0] + x, 6), round(at[1] + y, 6)]


def hidden(node):
    flag = node.child("hide")
    return any(n.atom == "hide" for n in node.children[1:]) or bool(flag and flag.value() in {None, "yes"})


def _library(root):
    container = root.child("lib_symbols")
    symbols = {n.value(): n for n in container.all("symbol")} if container else {}
    return symbols


def _parts(symbols, lib_id, unit, style, seen=()):
    """Graphics and pins of one unit/body style; derived symbols include their parent."""
    node = symbols.get(lib_id)
    if node is None:
        return None
    parts = []
    parent = node.child("extends")
    if parent and parent.value() not in seen and len(seen) < 8:
        prefix = lib_id.split(":", 1)[0] + ":" if ":" in lib_id else ""
        inherited = _parts(symbols, prefix + parent.value(), unit, style, (*seen, lib_id))
        parts.extend(inherited or [])
    for sub in node.all("symbol"):
        match = UNIT.search(sub.value() or "")
        if match and int(match.group(1)) in {0, unit} and int(match.group(2)) in {0, style}:
            parts.append(sub)
    return parts


def _graphic(node):
    kind = node.name
    if kind == "rectangle":
        a, b = point(node, "start"), point(node, "end")
        return [a, [b[0], a[1]], b, [a[0], b[1]], a]
    if kind == "circle":
        c, r = point(node, "center"), number(node.child("radius").value())
        return [[c[0] + r * math.cos(math.tau * i / 16), c[1] + r * math.sin(math.tau * i / 16)] for i in range(17)]
    if kind == "arc" and node.child("mid") is not None:
        return arc_points(point(node, "start"), point(node, "mid"), point(node, "end"))
    if kind == "arc":
        return [point(node, "start"), point(node, "end")]
    if kind in {"polyline", "bezier"}:
        pts = node.child("pts")
        return [[number(p.value()), number(p.value(2))] for p in pts.all("xy")] if pts else []
    return []


def _instance(node, sheet_path):
    """Reference and unit of this symbol on the requested sheet instance (UUID path)."""
    container = node.child("instances")
    unit = node.child("unit")
    fallback = dict(reference=properties(node).get("Reference", "?"), unit=int(unit.value()) if unit else 1)
    if container is None:
        return fallback
    for project in container.all("project"):
        for path in project.all("path"):
            if canonical_path(path.value()) == canonical_path(sheet_path):
                reference, number_node = path.child("reference"), path.child("unit")
                return dict(reference=reference.value() if reference else fallback["reference"],
                            unit=int(number_node.value()) if number_node else fallback["unit"])
    return None


def _uuid(node):
    child = node.child("uuid")
    return child.value() if child else None


def _label_box(at, text, size, angle):
    length = max(1.0, len(text) * size * 0.65)
    direction = [math.cos(math.radians(angle)), -math.sin(math.radians(angle))]
    end = [at[0] + direction[0] * length, at[1] + direction[1] * length]
    return bbox([at, end], size * 0.7)


def page_size(root):
    paper = root.child("paper")
    sizes = {"A5": (210, 148), "A4": (297, 210), "A3": (420, 297), "A2": (594, 420), "A1": (841, 594),
             "A0": (1189, 841), "A": (279.4, 215.9), "B": (431.8, 279.4), "C": (558.8, 431.8),
             "D": (863.6, 558.8), "E": (1117.6, 863.6), "USLetter": (279.4, 215.9),
             "USLegal": (355.6, 215.9), "USLedger": (431.8, 279.4)}
    page = [297.0, 210.0]
    if paper is not None:
        if paper.value() == "User":
            page = [number(paper.value(2)), number(paper.value(3))]
        elif paper.value() in sizes:
            page = list(sizes[paper.value()])
        if any(n.atom == "portrait" for n in paper.children[1:]):
            page = [min(page), max(page)]
    if min(page) < 10:
        raise PcbAiError("invalid_geometry", "Schematic page is too small")
    return page


def scene_sch(data, sheet_path, netlist=None):
    """Items of one sheet instance. ``sheet_path`` is the KiCad UUID path ("/root" or "/root/sheet")."""
    sheet_path = canonical_path(sheet_path)
    root = _schematic(data).root
    library = _library(root)
    items, warnings = [], set()
    page = page_size(root)
    pin_nets = (netlist or {}).get("pins", {})
    for node in root.all("symbol"):
        instance = _instance(node, sheet_path)
        if instance is None:
            continue  # this physical symbol belongs to another project/instance
        lib_id = node.child("lib_id").value() if node.child("lib_id") else None
        at = point(node)
        rotation = number(node.child("at").value(3, "0"))
        mirror_node = node.child("mirror")
        mirror = mirror_node.value() if mirror_node else None
        style_node = node.child("body_style") or node.child("convert")
        style = int(style_node.value()) if style_node else 1
        props = properties(node)
        reference = instance["reference"]
        parts = _parts(library, node.child("lib_name").value() if node.child("lib_name") else lib_id,
                       instance["unit"], style)
        if parts is None:
            warnings.add(f"Library symbol missing for {lib_id}; outline approximated")
            parts = []
        outline, pins = [], []
        pin_uuids = {p.value(): _uuid(p) for p in node.all("pin")}
        for part in parts:
            for graphic in part.children:
                if graphic.atom is None and graphic.name != "pin":
                    shape = [place(p, at, rotation, mirror) for p in _graphic(graphic)]
                    if shape:
                        outline.append(shape)
            for pin in part.all("pin"):
                local = point(pin)
                angle = number(pin.child("at").value(3, "0"))
                length_node = pin.child("length")
                length = number(length_node.value()) if length_node else 2.54
                tip = [local[0] + length * math.cos(math.radians(angle)),
                       local[1] + length * math.sin(math.radians(angle))]
                number_node, name_node = pin.child("number"), pin.child("name")
                pin_number = number_node.value() if number_node else ""
                start, end = place(local, at, rotation, mirror), place(tip, at, rotation, mirror)
                net = pin_nets.get((reference, pin_number))
                pins.append(dict(type="pin", uuid=pin_uuids.get(pin_number) or f"{_uuid(node)}:{pin_number}",
                                 parent=_uuid(node), reference=reference, number=pin_number,
                                 name=name_node.value() if name_node else "", electrical=pin.value(),
                                 hidden=hidden(pin), at=start, points=[start, end],
                                 bbox=bbox([start, end], 0.3), net=net, trusted=False))
        points = [p for shape in outline for p in shape] + [p for pin in pins for p in pin["points"]]
        item = dict(type="symbol", uuid=_uuid(node), reference=reference, value=props.get("Value", ""),
                    footprint=props.get("Footprint", ""), lib_id=lib_id, unit=instance["unit"],
                    at=at, rotation=rotation, mirror=mirror, power=reference.startswith("#"),
                    bbox=bbox(points or [at], 0.3), outline=outline, trusted=False)
        items.append(item)
        items.extend(pins)
    for kind in ("wire", "bus"):
        for node in root.all(kind):
            pts = node.child("pts")
            points = [[number(p.value()), number(p.value(2))] for p in pts.all("xy")] if pts else []
            if len(points) >= 2:
                items.append(dict(type=kind, uuid=_uuid(node), points=points, at=points[0],
                                  bbox=bbox(points, 0.2), net=None, trusted=False))
    for kind in ("junction", "no_connect"):
        for node in root.all(kind):
            at = point(node)
            items.append(dict(type=kind, uuid=_uuid(node), at=at, bbox=bbox([at], 0.5), trusted=False))
    for kind in LABELS:
        for node in root.all(kind):
            at = point(node)
            angle = number(node.child("at").value(3, "0"))
            text = node.value() if kind != "netclass_flag" else node.value()
            size = 1.27
            effects = node.child("effects")
            font = effects.child("font") if effects else None
            if font and font.child("size"):
                size = number(font.child("size").value())
            shape = node.child("shape")
            items.append(dict(type="label", kind=kind, uuid=_uuid(node), text=text or "", at=at, angle=angle,
                              shape=shape.value() if shape else None, bbox=_label_box(at, text or "", size, angle),
                              net=None, trusted=False))
    for node in root.all("sheet"):
        at, size = point(node), point(node, "size")
        props = properties(node)
        child = sheet_path.rstrip("/") + "/" + (_uuid(node) or "")
        corners = [at, [at[0] + size[0], at[1]], [at[0] + size[0], at[1] + size[1]], [at[0], at[1] + size[1]]]
        pins = []
        for pin in node.all("pin"):
            pin_at = point(pin)
            pins.append(dict(type="sheet_pin", uuid=_uuid(pin), parent=_uuid(node), text=pin.value(),
                             electrical=pin.value(2), at=pin_at, bbox=bbox([pin_at], 0.8), net=None,
                             trusted=False))
        items.append(dict(type="sheet", uuid=_uuid(node), name=props.get("Sheetname", props.get("Sheet name", "")),
                          file=props.get("Sheetfile", props.get("Sheet file", "")), instance=child, at=at,
                          size=size, polygon=corners, bbox=bbox(corners), trusted=False))
        items.extend(pins)
    stamps = [s for s in sheet_path.split("/")[2:] if s]
    tstamps = "/" + "".join(s + "/" for s in stamps)
    names = next((p["names"] for p in (netlist or {}).get("pages", []) if p["tstamps"] == tstamps), None)
    _propagate(items, netlist or {}, warnings, names)
    if len(items) > 200000:
        raise PcbAiError("scene_too_large", "Scene exceeds the item limit")
    return dict(space="sch", units="mm", sheet=sheet_path, page=page, bbox=[0, 0, page[0], page[1]],
                items=items, warnings=sorted(warnings))


def _key(p):
    return (round(p[0], 3), round(p[1], 3))


def _on_segment(p, a, b, tolerance=1e-3):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    if length == 0:
        return math.dist(p, a) <= tolerance
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length
    if t < -1e-9 or t > 1 + 1e-9:
        return False
    return math.dist(p, [a[0] + t * dx, a[1] + t * dy]) <= tolerance


def _propagate(items, netlist, warnings, sheet_names):
    """Assign wires and labels the net of KiCad-netlisted pins they touch; never infer a name otherwise."""
    wires = [i for i in items if i["type"] == "wire"]
    anchors = [i for i in items if i["type"] in {"pin", "label", "sheet_pin", "junction"}]
    parent = list(range(len(wires) + len(anchors)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        parent[find(a)] = find(b)

    # Connection points: wire ends (node = wire index) and anchors (node = len(wires) + offset).
    cell = 5.0
    grid = {}
    for index, wire in enumerate(wires):
        for p in (wire["points"][0], wire["points"][-1]):
            grid.setdefault((math.floor(p[0] / cell), math.floor(p[1] / cell)), []).append((p, index))
    for offset, anchor in enumerate(anchors):
        p = anchor["at"]
        grid.setdefault((math.floor(p[0] / cell), math.floor(p[1] / cell)), []).append((p, len(wires) + offset))
    for index, wire in enumerate(wires):
        for a, b in zip(wire["points"], wire["points"][1:], strict=False):
            x0, x1 = sorted((a[0], b[0]))
            y0, y1 = sorted((a[1], b[1]))
            for gx in range(math.floor((x0 - 0.01) / cell), math.floor((x1 + 0.01) / cell) + 1):
                for gy in range(math.floor((y0 - 0.01) / cell), math.floor((y1 + 0.01) / cell) + 1):
                    for p, node in grid.get((gx, gy), []):
                        if node != index and _on_segment(p, a, b):
                            union(index, node)
    # Pins touching pins directly (no wire) are connected in KiCad as well.
    by_point = {}
    for offset, anchor in enumerate(anchors):
        by_point.setdefault(_key(anchor["at"]), []).append(len(wires) + offset)
    for group in by_point.values():
        for other in group[1:]:
            union(group[0], other)
    clusters = {}
    for offset, anchor in enumerate(anchors):
        if anchor["type"] == "pin" and anchor.get("net"):
            clusters.setdefault(find(len(wires) + offset), set()).add(anchor["net"])
    # A cluster without netlisted pins may still carry a label. Use KiCad's own naming only when that exact
    # net exists in the netlist (global "X", local/hierarchical "<sheet names>X"); otherwise leave it unknown.
    known = netlist.get("members", {})
    for offset, anchor in enumerate(anchors):
        node = find(len(wires) + offset)
        if anchor["type"] != "label" or node in clusters or not anchor["text"] or sheet_names is None:
            continue
        names = [anchor["text"]] if anchor["kind"] == "global_label" else [sheet_names + anchor["text"]]
        found = {n for n in names if n in known}
        if len(found) == 1:
            clusters.setdefault(node, set()).update(found)
    conflicts = 0
    for index, wire in enumerate(wires):
        names = clusters.get(find(index), set())
        if len(names) == 1:
            wire["net"] = next(iter(names))
        elif len(names) > 1:
            conflicts += 1
    for offset, anchor in enumerate(anchors):
        if anchor["type"] in {"label", "sheet_pin"}:
            names = clusters.get(find(len(wires) + offset), set())
            if len(names) == 1:
                anchor["net"] = next(iter(names))
    if conflicts:
        warnings.add(f"{conflicts} wires touch pins of different KiCad nets; their net is left unknown")
    if netlist and any(i["type"] == "wire" and i["net"] is None for i in wires):
        warnings.add("Wires without a netlisted pin on this page have no net name")


def parse_netlist(data):
    """KiCad XML netlist → pages, (reference, pin) → net and net members. Nothing is inferred."""
    if len(data) > 64 * 1024 * 1024 or b"<!ENTITY" in data.upper() or b"<!DOCTYPE" in data.upper():
        raise PcbAiError("invalid_report", "Netlist exceeds limits or declares entities")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise PcbAiError("invalid_report", "KiCad netlist is not valid XML") from exc
    pages = []
    for sheet in root.iter("sheet"):
        source = sheet.find("title_block/source")
        pages.append(dict(number=sheet.get("number"), names=sheet.get("name"), tstamps=sheet.get("tstamps"),
                          source=source.text if source is not None else None))
    components = {}
    for comp in root.iter("comp"):
        path = comp.find("sheetpath")
        source = comp.find("libsource")
        components[comp.get("ref")] = dict(value=(comp.findtext("value") or ""),
                                           part=source.get("part") if source is not None else None,
                                           tstamps=path.get("tstamps") if path is not None else None,
                                           names=path.get("names") if path is not None else None)
    pins, members = {}, {}
    for net in root.iter("net"):
        name = net.get("name")
        for node in net.iter("node"):
            key = (node.get("ref"), node.get("pin"))
            pins[key] = name
            members.setdefault(name, []).append(dict(reference=key[0], pin=key[1],
                                                     sheet=components.get(key[0], {}).get("tstamps"),
                                                     function=node.get("pinfunction"), type=node.get("pintype")))
    if not pages:
        raise PcbAiError("invalid_report", "Netlist has no sheets")
    return dict(pages=pages, components=components, pins=pins, members=members)


def hit_test_sch(scene, x, y, tolerance=0.5):
    p = [number(x), number(y)]
    hits = []
    for item in scene["items"]:
        b = item["bbox"]
        if not (b[0] - tolerance <= p[0] <= b[2] + tolerance and b[1] - tolerance <= p[1] <= b[3] + tolerance):
            continue
        if item["type"] in {"wire", "bus", "pin"}:
            d = min(_distance(p, a, c) for a, c in zip(item["points"], item["points"][1:], strict=False))
        elif item["type"] in {"junction", "no_connect", "sheet_pin"}:
            d = math.dist(p, item["at"])
        else:
            d = math.hypot(max(b[0] - p[0], 0, p[0] - b[2]), max(b[1] - p[1], 0, p[1] - b[3]))
        if d <= tolerance:
            hits.append(dict(item, distance_mm=d))
    rank = {"pin": 0, "sheet_pin": 1, "junction": 2, "label": 3, "wire": 4, "bus": 5, "no_connect": 6,
            "symbol": 7, "sheet": 8}
    # Within a small radius the item type decides (pin before wire before symbol), farther away the distance.
    # Specific items (pin, wire, label…) win over the symbol/sheet box that contains them.
    def key(i):
        near = i["distance_mm"] <= tolerance * 0.4
        area = i["type"] in {"symbol", "sheet"}
        return (area, 0 if near else 1, 0 if near else i["distance_mm"], rank[i["type"]], i["distance_mm"])
    return sorted(hits, key=key)[:20]


def _distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length)) if length else 0
    return math.dist(p, [a[0] + t * dx, a[1] + t * dy])
