"""Untrusted engine outputs may alter only explicitly permitted PCB geometry."""
import uuid
from collections import Counter

from pcbai.core.contract import PcbAiError
from pcbai.kicad.board import board
from pcbai.pcb.edit import Edits, footprint_by_reference, net_names, plan_move, quoted
from pcbai.sch.model import properties
from pcbai.views import angle, number, xy

ROUTES = {"segment", "arc", "via"}
FILLS = {"filled_polygon", "filled_areas_thickness"}


def identity(node):
    entry = node.child("uuid") or node.child("tstamp")
    return canonical_uuid(entry.value()) if entry else None


def canonical_uuid(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        return value.lower() if isinstance(value, str) else value


def locked(node):
    entry = node.child("locked")
    return any(n.atom == "locked" for n in node.children) or (entry is not None and entry.value() != "no")


def signatures(data, nodes):
    return Counter(data[n.start:n.end] for n in nodes)


def protected_differences(before, after, old_nodes, new_nodes):
    old, new = signatures(before, old_nodes), signatures(after, new_nodes)
    removed, added = old - new, new - old
    records = []
    for data, nodes, counts, reason in ((before, old_nodes, removed, "Protected node removed/changed"),
                                       (after, new_nodes, added, "Protected node added/changed")):
        for node in nodes:
            key = data[node.start:node.end]
            if counts[key]:
                records.append(dict(type=node.name, uuid=identity(node), reason=reason))
                counts[key] -= 1
    return records[:50]


def uuid_check(root):
    found = set()
    pending = [root]
    while pending:
        node = pending.pop()
        for child in node.children:
            if child.atom is not None:
                continue
            if child.name in {"uuid", "tstamp"}:
                key = canonical_uuid(child.value())
                if key is None or key in found:
                    raise PcbAiError("engine_touched_foreign_items", "Engine input/output has missing/duplicate UUIDs",
                                     details={"uuid": key})
                found.add(key)
            else:
                pending.append(child)
    return found


def guard(before, after, *, operation="route", reroute=False, allow_flip=False):
    source, output = board(before), board(after)
    if [n.atom for n in source.children if n.atom is not None] != [n.atom for n in output.children if n.atom is not None]:
        raise PcbAiError("engine_touched_foreign_items", "Engine changed root-level atoms")
    known = uuid_check(source)
    uuid_check(output)
    if operation not in {"route", "place"}:
        raise PcbAiError("invalid_arguments", "Unknown engine guard operation")
    diffs, moved = [], []

    def changed(node, reason):
        diffs.append(dict(type=node.name, uuid=identity(node), reason=reason))

    if operation == "route":
        # Headers, unknown future nodes and all footprints are protected, including their whitespace.
        def protected(root):
            return [n for n in root.children if n.atom is None and n.name not in ROUTES | {"zone"}]
        if signatures(before, protected(source)) != signatures(after, protected(output)):
            diffs.extend(protected_differences(before, after, protected(source), protected(output)))
        old = {identity(n): n for n in source.children if n.name in ROUTES}
        new = {identity(n): n for n in output.children if n.name in ROUTES}
        for key, node in old.items():
            other = new.get(key)
            if other is None:
                if not reroute or locked(node):
                    changed(node, "Existing/locked route deleted")
            elif before[node.start:node.end] != after[other.start:other.end]:
                changed(node, "Existing route modified")
        table, names = net_names(source)
        layers = source.child("layers")
        copper = {n.value() for n in layers.children[1:] if n.value().endswith(".Cu")} if layers else set()
        for key, node in new.items():
            if key in old:
                continue
            try:
                uuid.UUID(key)
            except (ValueError, TypeError, AttributeError):
                changed(node, "New route requires a valid unique UUID")
            if key in known:
                changed(node, "New route reuses a protected UUID")
            net = node.child("net")
            if net is None or (table and net.value() not in table) or (
                    not table and (net.value(2) is not None or net.value() not in names)):
                changed(node, "New route has an undefined net")
            if net is not None and table and net.value(2) is not None and table.get(net.value()) != net.value(2):
                changed(node, "New route net number/name mismatch")
            layer = node.child("layer")
            via_layers = node.child("layers")
            if node.name == "via":
                if via_layers is None or any(a.atom not in copper for a in via_layers.children[1:]):
                    changed(node, "Via has unknown/non-copper layers")
                xy(node)
                diameter, drill = node.child("size"), node.child("drill")
                if diameter is None or drill is None or not 0 < number(drill.value()) < number(diameter.value()):
                    changed(node, "Invalid via diameter/drill")
            else:
                if layer is None or layer.value() not in copper:
                    changed(node, "Track has unknown/non-copper layer")
                width = node.child("width")
                if width is None or number(width.value()) <= 0:
                    changed(node, "Invalid track width")
                xy(node, "start")
                xy(node, "end")
                if node.name == "arc":
                    xy(node, "mid")
        old_zones = {identity(n): n for n in source.all("zone")}
        new_zones = {identity(n): n for n in output.all("zone")}
        if old_zones.keys() != new_zones.keys():
            diffs.append(dict(type="zone", uuid=None, reason="Zone added or deleted"))
        for key in old_zones.keys() & new_zones.keys():
            a, b = old_zones[key], new_zones[key]
            # Compare actual bytes with permitted fill subtrees removed; protects zone scalar atoms too.
            if without(before, a, FILLS) != without(after, b, FILLS):
                changed(a, "Zone settings/outline changed")
    else:
        def protected(root):
            return [n for n in root.children if n.atom is None and n.name != "footprint"]
        if signatures(before, protected(source)) != signatures(after, protected(output)):
            diffs.extend(protected_differences(before, after, protected(source), protected(output)))
        old = {identity(n): n for n in source.all("footprint")}
        new = {identity(n): n for n in output.all("footprint")}
        if old.keys() != new.keys():
            diffs.append(dict(type="footprint", uuid=None, reason="Footprint added/deleted"))
        for key in old.keys() & new.keys():
            a, b = old[key], new[key]
            if before[a.start:a.end] == after[b.start:b.end]:
                continue
            if locked(a):
                changed(a, "Locked footprint moved")
                continue
            layer_a, layer_b = a.child("layer"), b.child("layer")
            if layer_a is None or layer_b is None:
                changed(a, "Missing footprint layer")
                continue
            flipped = layer_a.value() != layer_b.value()
            if flipped and not allow_flip:
                changed(a, "Side change not permitted in this placement mode")
                continue
            ref = properties(a).get("Reference") or next((n.value(2) for n in a.all("fp_text")
                                                         if n.value() == "reference"), None)
            if not ref:
                changed(a, "Footprint has no unique reference")
                continue
            pos = xy(b)
            planned = plan_move(before, ref, *pos, angle(b), "back" if layer_b.value() == "B.Cu" else "front")
            expected = footprint_by_reference(board(planned["data"]), ref)
            # No value, pad/net, courtyard or graphical content may change beyond measured move/flip rules.
            if placement_bytes(planned["data"], expected) != placement_bytes(after, b):
                changed(a, "Footprint changed beyond the permitted move/rotation/flip")
            moved.append(dict(reference=ref, uuid=key, before=xy(a), after=pos))
    if diffs:
        raise PcbAiError("engine_touched_foreign_items", "Engine changed protected PCB data",
                         details={"differences": diffs[:50]})
    return dict(clean=True, moved=moved)


def placement_bytes(data, footprint):
    """Only the movable top-level position may omit its zero angle; all other bytes stay protected."""
    value = data[footprint.start:footprint.end]
    at = footprint.child("at")
    if at is not None and len(at.children) == 3 and all(n.atom is not None for n in at.children):
        offset = at.end - footprint.start - 1
        value = value[:offset] + b" 0" + value[offset:]
    return value


def without(data, node, names):
    # Every protected child retains its exact bytes; whitespace around permitted fills is immaterial.
    return tuple(data[n.start:n.end] for n in node.children if n.name not in names)


def replace_fills(candidate, filled):
    """Transplant only KiCad-computed fill nodes, preserving headers, net syntax and all zone settings."""
    edits = Edits(candidate)
    filled_zones = {identity(n): n for n in board(filled).all("zone")}
    for zone in edits.doc.root.all("zone"):
        other = filled_zones.get(identity(zone))
        if other is None:
            raise PcbAiError("engine_touched_foreign_items", "Zone lost during refill")
        for node in zone.children:
            if node.name in FILLS:
                edits.changes.append((node.start, node.end, b""))
        nodes = [filled[n.start:n.end].decode("utf-8") for n in other.children if n.name in FILLS]
        if nodes:
            edits.insert(zone.end - 1, " " + " ".join(nodes))
    changed = edits.result()
    guard(candidate, changed)
    return changed


def rebase_routes(original, baseline, routed):
    """Check pcbnew-normalized before/after, then transplant route deltas into original file bytes."""
    # pcbnew serializes input, but the SES importer must not change anything beyond the route nodes.
    guard(baseline, routed, reroute=True)
    a, b = board(baseline), board(routed)
    old = {identity(n): n for n in a.children if n.name in ROUTES}
    new = {identity(n): n for n in b.children if n.name in ROUTES}
    original_root = board(original)
    originals = {identity(n): n for n in original_root.children if n.name in ROUTES}
    edits = Edits(original)
    for key in old.keys() - new.keys():
        if key not in originals:
            raise PcbAiError("engine_touched_foreign_items", "Bridge lost route identity")
        n = originals[key]
        edits.changes.append((n.start, n.end, b""))
    table, names = net_names(original_root)
    numbers = {v: k for k, v in table.items()}
    for key in new.keys() - old.keys():
        node = new[key]
        data = routed[node.start:node.end]
        item = Edits(data)
        net = item.doc.root.child("net")
        base_table, _ = net_names(a)
        name = net.value(2) or base_table.get(net.value(), net.value())
        if name not in names:
            raise PcbAiError("engine_touched_foreign_items", "Bridge introduced unknown net")
        item.changes.append((net.start, net.end, (f"(net {numbers[name]})" if table else
                                                f"(net {quoted(name)})").encode("utf-8")))
        edits.insert(original_root.end - 1, "\n  " + item.result().decode("utf-8") + "\n")
    result = edits.result()
    guard(original, result, reroute=True)
    return result
