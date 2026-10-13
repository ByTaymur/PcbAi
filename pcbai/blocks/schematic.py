"""Compose a trusted passive recipe in bytes; one document, no project writes."""
import math
import re

from pcbai.blocks.registry import expand
from pcbai.core.contract import PcbAiError
from pcbai.ir.plan import bounded_json
from pcbai.kicad.files import digest
from pcbai.parts.library import symbol, verify_part
from pcbai.pcb.edit import Edits, fmt
from pcbai.sch.edit import (cache_insert, cached_info, definitions, endpoint, location,
                            pins, plan_add_symbol, plan_labels)
from pcbai.sch.model import _schematic
from pcbai.sch.scene import hidden, scene_sch
from pcbai.sexpr import Document
from pcbai.views import bbox, number


def fail(code, message):
    raise PcbAiError(code, message)


def ordinary(info):
    root = Document(info["data"]).root
    if root.child("power") or info["units"] != [1]:
        fail("incompatible_cache", "Passive recipes require an ordinary single-unit non-power symbol")
    if any(hidden(pin) for unit in root.all("symbol") for pin in unit.all("pin")):
        fail("incompatible_cache", "Hidden pins are not supported by passive recipes")
    active = pins(info)
    if len(active) != 2 or {p["number"] for p in active} != {"1", "2"} or any(p["electrical_type"] != "passive" for p in active):
        fail("incompatible_cache", "Passive recipe pins must be unique visible passive 1 and 2")
    return sorted((p["number"], *p["at"], p["rotation"], p["electrical_type"], p["shape"]) for p in active)


def reserve(parts, references):
    # Conservatively reserve case and leading-zero equivalents without unbounded int parsing.
    used = set()
    for existing in references:
        match = re.fullmatch(r"([A-Za-z]+)([0-9]+)", existing["reference"])
        if match:
            used.add((match[1].upper(), match[2].lstrip("0") or "0"))
    allocated = {}
    for part in parts:
        prefix = "R" if part["symbol"] == "Device:R" else "C"
        for n in range(1, 10001):
            if (prefix, str(n)) not in used:
                allocated[part["id"]] = prefix + str(n)
                used.add((prefix, str(n)))
                break
        else:
            fail("reference_exhausted", "No free bounded reference for " + prefix)
    return allocated


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def existing_text_boxes(root):
    """Conservative boxes for saved visible fields/text missing from the scene model."""
    supported = {"version", "generator", "generator_version", "uuid", "paper", "title_block", "lib_symbols",
                 "symbol", "wire", "bus", "junction", "no_connect", "label", "global_label", "hierarchical_label",
                 "netclass_flag", "sheet", "sheet_instances", "symbol_instances", "bus_alias", "text",
                 "embedded_fonts", "embedded_files"}
    for child in root.children:
        if child.atom is None and child.name not in supported:
            fail("unsupported_layout", "Cannot bound saved schematic element: " + str(child.name))
    text_nodes = list(root.all("text"))
    for node_kind in ("symbol", "sheet"):
        for owner in root.all(node_kind):
            text_nodes.extend(owner.all("property"))
    answer = []
    for node in text_nodes:
        effects, at = node.child("effects"), node.child("at")
        if hidden(node) or (effects is not None and hidden(effects)):
            continue
        if at is None:
            fail("unsupported_layout", "Visible saved text/field has no position")
        text = node.value(2, "") if node.name == "property" else node.value(default="")
        if not text:
            continue
        font = effects.child("font") if effects else None
        size = font.child("size") if font else None
        sx, sy = (number(size.value()), number(size.value(2))) if size else (1.27, 1.27)
        x, y = number(at.value()), number(at.value(2))
        if any(not math.isfinite(v) for v in (x, y, sx, sy)) or sx <= 0 or sy <= 0:
            fail("unsupported_layout", "Visible text has invalid position/font")
        lines = text.splitlines() or [text]
        # Covers arbitrary justification/rotation conservatively; no glyph-level precision claim.
        radius = math.hypot(max(1, max(map(len, lines))) * sx, max(1, len(lines)) * sy) + max(sx, sy)
        answer.append(bbox([[x, y]], radius))
    return answer


def plan_block(data, args, context):
    for key in ("block", "params", "instance", "x_mm", "y_mm"):
        if key not in args:
            fail("invalid_arguments", "add_block preview requires " + key)
    bounded_json(args["params"])
    instance = args["instance"]
    if not isinstance(instance, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", instance):
        fail("invalid_arguments", "Block instance must be a scalar ASCII identifier of at most 32 characters")
    block = expand(args["block"], args["params"])
    root = _schematic(data).root
    origin = location(root, args["x_mm"], args["y_mm"])
    prefix = "PcbAi_" + instance + "_"
    for kind in ("label", "global_label", "hierarchical_label", "netclass_flag"):
        if any((node.value() or "").startswith(prefix) for node in root.all(kind)):
            fail("namespace_collision", "Block namespace already appears on the target sheet")
    refs = reserve(block["parts"], context["references"])
    frozen, hashes, library_hashes = {}, {}, {}
    for part in block["parts"]:
        lib = part["symbol"]
        if lib in frozen:
            continue
        installed = symbol(lib)
        previous = library_hashes.setdefault(installed["path"], installed["library_sha256"])
        if previous != installed["library_sha256"]:
            fail("stale_library", "Recipe cannot mix revisions of the same installed library")
        effective = cached_info(data, lib) if lib in definitions(root) else installed
        if ordinary(installed) != ordinary(effective):
            fail("incompatible_cache", "Cached recipe symbol pin geometry/type differs from installed definition")
        pair = verify_part(lib, part["footprint"])
        if pair["symbol_library_sha256"] != installed["library_sha256"]:
            fail("stale_library", "Symbol library changed while freezing recipe")
        if not pair["pin_pad_match"]:
            fail("incompatible_pins", "Recipe symbol/footprint pair is incompatible")
        frozen[lib] = effective
        hashes[lib] = dict(source="project_cache" if lib in definitions(root) else "kicad",
                           definition_sha256=digest(effective["data"]),
                           installed_library_sha256=installed["library_sha256"],
                           footprint=part["footprint"], footprint_sha256=pair["footprint_sha256"], pin_pad_match=True)
    # Insert only the inspected frozen bytes before calling any ordinary authoring helper.
    prepared = data
    for lib, info in frozen.items():
        if lib not in definitions(_schematic(prepared).root):
            edits = Edits(prepared)
            cache_insert(edits, info)
            prepared = edits.result()
    uuids = []
    fields = []
    for i, part in enumerate(block["parts"]):
        at = [origin[0] + i * 50.8, origin[1]]
        added = plan_add_symbol(prepared, dict(lib_id=part["symbol"], reference=refs[part["id"]],
            value=part["value"], footprint=part["footprint"], x_mm=at[0], y_mm=at[1]), context)
        prepared = added["data"]
        uuids.append(added["symbol_uuid"])
        edits = Edits(prepared)
        node = next(n for n in edits.doc.root.all("symbol") if n.child("uuid").value() == uuids[-1])
        # Keep visible fields above the passive body, clear of the two port-label rows.
        for name, text, offset in (("Reference", refs[part["id"]], -10.16), ("Value", part["value"], -7.62)):
            field = next(p for p in node.all("property") if p.value() == name).child("at")
            edits.atom(field.children[1], fmt(at[0]))
            edits.atom(field.children[2], fmt(at[1] + offset))
            half_width = max(1, len(text) * 1.27 * .65) / 2
            fields.append([at[0] - half_width, at[1] + offset - .889, at[0] + half_width, at[1] + offset + .889])
        prepared = edits.result()
    expected, ports = {}, {}
    aliases = {}
    for port, members in block["port_pins"].items():
        key = tuple(sorted((p["part"], p["pin"]) for p in members))
        name = aliases.setdefault(key, prefix + port)
        ports[port] = name
        expected.setdefault(name, [dict(reference=refs[p], pin=n, unit=1) for p, n in key])
    label_ids = []
    for name, members in expected.items():
        for spec in members:
            anchor = endpoint(prepared, spec, context)
            added = plan_labels(prepared, dict(name=name, kind="local", x_mm=anchor["at"][0], y_mm=anchor["at"][1]), context)
            prepared = added["data"]
            label_ids.extend(added["label_uuids"])
    before_scene = scene_sch(data, context["sheet_path"])
    after_scene = scene_sch(prepared, context["sheet_path"])
    generated = [item for item in after_scene["items"] if item["uuid"] in set(uuids + label_ids)]
    boxes = fields + [item["bbox"] for item in generated]
    width, height = after_scene["page"]
    if any(b[0] < 0 or b[1] < 0 or b[2] > width or b[3] > height for b in boxes):
        fail("layout_outside_page", "Whole block body/labels/visible fields must fit on the page")
    old_boxes = [old["bbox"] for old in before_scene["items"]] + existing_text_boxes(root)
    if any(overlaps(a, old) for a in boxes for old in old_boxes):
        fail("layout_collision", "Block overlaps existing saved schematic geometry/labels")
    body_boxes = [item["bbox"] for item in generated if item["type"] == "symbol"]
    if any(overlaps(a, b) for i, a in enumerate(body_boxes) for b in body_boxes[i + 1:]):
        fail("layout_collision", "Recipe symbol bodies overlap")
    return dict(data=prepared, block=block["block"], instance=instance, maturity=0,
                affected_references=list(refs.values()), reference_map=refs, symbol_uuids=uuids,
                label_uuids=label_ids, port_nets=ports, expected_nets=expected, library_inputs=hashes,
                calculation=block["calculation"], layout_bbox=[min(b[0] for b in boxes), min(b[1] for b in boxes),
                                                            max(b[2] for b in boxes), max(b[3] for b in boxes)],
                warnings=block["warnings"] + ["Isolated local scalar nets; no existing net is reused",
                    "Layout bounds use approximate text boxes; inspect the rendered candidate", "No persistent IR mapping or multi-file compiler"])


def measure_topology(plan, netlist):
    actual, used = {}, set()
    for name, members in plan["expected_nets"].items():
        canonical = {netlist["pins"].get((p["reference"], p["pin"])) for p in members}
        if len(canonical) != 1 or None in canonical:
            fail("connectivity_failed", "Not all block pins belong to the expected native net: " + name)
        net = next(iter(canonical))
        if net in used:
            fail("connectivity_failed", "KiCad merged distinct block nets")
        expected = {(p["reference"], p["pin"]) for p in members}
        measured = {(p["reference"], p["pin"]) for p in netlist["members"][net]}
        if measured != expected:
            fail("connectivity_failed", "Block net contains missing/extra native members: " + name)
        used.add(net)
        actual[name] = dict(name=net, members=netlist["members"][net])
    return actual
