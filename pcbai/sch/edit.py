"""Byte-preserving, single-sheet schematic authoring planners.

The project cache is authoritative. Shared physical sheets are refused: one
file write cannot isolate one logical instance. No planner writes a file.
"""
import re
import uuid
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.kicad.files import digest, project_files, within
from pcbai.parts.library import flatten, identifier, inspect_symbol, symbol as installed_symbol
from pcbai.pcb.edit import Edits, fmt, quoted
from pcbai.pcb.engine_guard import uuid_check
from pcbai.sch.model import (_in_project, _instances, _schematic, canonical_id,
                            canonical_path, properties, symbols)
from pcbai.sch.scene import UNIT, page_size, place, point
from pcbai.sexpr import Document
from pcbai.views import number


def text(value, what="Text"):
    if (not isinstance(value, str) or not value or len(value) > 256 or
            any(ord(c) < 32 or 127 <= ord(c) <= 159 or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        raise PcbAiError("invalid_arguments", what + " must be nonempty text without control characters")
    return value


def hierarchy(session, document):
    """Resolve saved sheet paths without guessing from filenames or display refs."""
    root_document = Path(session.project).with_suffix(".kicad_sch").name
    project = Path(session.project).stem
    root = _schematic(session.validate(root_document)[0].read_bytes()).root
    root_id = root.child("uuid")
    if root_id is None:
        raise PcbAiError("invalid_document", "Root schematic has no UUID")
    pages = []

    def visit(name, instance, ancestry=(), incoming=(), owner=root_document):
        path = within(session.root, name)
        if path in ancestry or len(ancestry) >= 32 or len(pages) >= 1024:
            raise PcbAiError("invalid_document", "Schematic hierarchy is cyclic or too large")
        data = path.read_bytes()
        node = _schematic(data).root
        uuid_check(node)
        pages.append(dict(document=path.relative_to(session.root).as_posix(), instance=instance, data=data,
                          incoming=incoming, owner=owner))
        for sheet in node.all("sheet"):
            props = properties(sheet)
            filename = props.get("Sheetfile") or props.get("Sheet file")
            sheet_id = sheet.child("uuid")
            if not filename or sheet_id is None:
                raise PcbAiError("invalid_document", "Sheet has no file or UUID")
            filename = filename.replace("${KIPRJMOD}", str(session.root))
            child = within(session.root, str(path.parent / filename))
            visit(child.relative_to(session.root).as_posix(), instance + "/" + canonical_id(sheet_id.value()),
                  (*ancestry, path), (*incoming, (sheet, instance)), owner)

    visit(root_document, "/" + canonical_id(root_id.value()))
    # A blank shared child has no symbol records to disclose its foreign use.
    # Check other saved project roots inside the authorized boundary as well.
    projects = [p for p in project_files(session.root) if p.suffix == ".kicad_pro"]
    if len(projects) > 64:
        raise PcbAiError("invalid_document", "Too many project roots to establish isolated authoring")
    for project_file in projects:
        if project_file == within(session.root, session.project):
            continue
        schematic = project_file.with_suffix(".kicad_sch")
        if not schematic.exists():
            continue  # PCB-only project cannot reference a saved schematic hierarchy.
        foreign = _schematic(within(session.root, str(schematic)).read_bytes()).root
        foreign_id = foreign.child("uuid")
        if foreign_id is None:
            raise PcbAiError("invalid_document", "Other authorized project has no root schematic UUID")
        visit(schematic.relative_to(session.root).as_posix(), "/" + canonical_id(foreign_id.value()),
              owner=schematic.relative_to(session.root).as_posix())
    wanted = within(session.root, document)
    matches = [p for p in pages if within(session.root, p["document"]) == wanted]
    if len(matches) != 1:
        raise PcbAiError("shared_sheet" if matches else "unknown_sheet",
                         "Authoring requires exactly one logical instance of the physical sheet")
    for node in _schematic(matches[0]["data"]).root.all("symbol"):
        for record in _instances(node):
            if (not _in_project(record, project, root_id.value()) or
                    record["sheet_path"] not in {None, matches[0]["instance"]}):
                raise PcbAiError("shared_sheet", "Physical sheet has symbol records for another project/instance")
    for node in _schematic(matches[0]["data"]).root.all("sheet"):
        check_sheet_records(node, project, root_id.value(), matches[0]["instance"])
    for node, parent_instance in matches[0]["incoming"]:
        check_sheet_records(node, project, root_id.value(), parent_instance)
    references = []
    for page in pages:
        if page["owner"] != root_document:
            continue
        references.extend(dict(s, document=page["document"]) for s in
                          symbols(page["data"], project, root_id.value())
                          if s["sheet_path"] in {None, page["instance"]})
    return dict(project=project, root_uuid=canonical_id(root_id.value()), sheet_path=matches[0]["instance"],
                check_document=root_document, references=references)


def check_sheet_records(node, project, root_uuid, parent_instance):
    container = node.child("instances")
    if container is None:
        return
    records = 0
    seen = set()
    for owner in container.all("project"):
        for path in owner.all("path"):
            page = path.child("page")
            if owner.value() is None or not path.value() or page is None or not page.value():
                raise PcbAiError("invalid_document", "Incomplete hierarchical sheet instance record")
            instance = dict(project=owner.value(), sheet_path=canonical_path(path.value()))
            if not _in_project(instance, project, root_uuid) or instance["sheet_path"] != parent_instance:
                raise PcbAiError("shared_sheet", "Sheet or its ancestor belongs to another project/instance")
            if instance["sheet_path"] in seen:
                raise PcbAiError("invalid_document", "Duplicate sheet instance records")
            seen.add(instance["sheet_path"])
            records += 1
    if not records:
        raise PcbAiError("invalid_document", "Sheet instances contain no usable records")


def definitions(root):
    cache = root.child("lib_symbols")
    answer = {}
    for node in cache.all("symbol") if cache else []:
        if node.value() in answer:
            raise PcbAiError("invalid_library", "Duplicate cached symbol definitions")
        answer[node.value()] = node
    return answer


def cached_info(data, lib_id):
    root = _schematic(data).root
    entries = definitions(root)
    if lib_id not in entries:
        raise PcbAiError("invalid_library", "Instantiated symbol is missing from the project cache")
    flat = flatten(data, entries, lib_id, lib_id, cached=True)
    return dict(inspect_symbol(flat, lib_id), source="project_cache", definition_sha256=digest(flat))


def source_info(data, lib_id):
    identifier(lib_id)
    if lib_id in definitions(_schematic(data).root):
        return cached_info(data, lib_id), False
    info = installed_symbol(lib_id)
    return dict(info, definition_sha256=digest(info["data"])), True


def pins(info, unit=1, style=1):
    """All active pins, including common units/body style, with literal numbers."""
    root = Document(info["data"]).root
    answer = []
    active_unit = False
    common_only = all(UNIT.search(sub.value() or "") and int(UNIT.search(sub.value()).group(1)) == 0
                      for sub in root.all("symbol"))
    for sub in root.all("symbol"):
        match = UNIT.search(sub.value() or "")
        if not match:
            raise PcbAiError("invalid_library", "Invalid cached symbol unit/body style")
        subunit, substyle = map(int, match.groups())
        if subunit not in {0, unit} or substyle not in {0, style}:
            continue
        active_unit |= subunit == unit
        for pin in sub.all("pin"):
            label = pin.child("number")
            if label is None or not label.value():
                raise PcbAiError("invalid_library", "Pin has no literal number")
            answer.append(dict(number=label.value(), at=point(pin), electrical_type=pin.value(),
                               shape=pin.value(2), rotation=number(pin.child("at").value(3, "0"))))
    if not active_unit and not (unit == 1 and common_only and root.all("symbol")):
        raise PcbAiError("invalid_arguments", "Requested unit/body style does not exist")
    return answer


def location(root, x, y):
    x, y = number(str(x)), number(str(y))
    page = page_size(root)
    if not 0 <= x <= page[0] or not 0 <= y <= page[1]:
        raise PcbAiError("invalid_arguments", "Position must be inside the schematic page")
    # Electrical anchors follow the standard 50 mil grid; do not silently snap.
    if any(abs(v / 1.27 - round(v / 1.27)) > 1e-6 for v in (x, y)):
        raise PcbAiError("off_grid", "Use a 1.27 mm (50 mil) schematic grid")
    return [x, y]


def cache_insert(edits, info):
    root = edits.doc.root
    cache = root.child("lib_symbols")
    raw = info["data"].decode("utf-8")
    if cache:
        edits.insert(cache.end - 1, "\n" + raw + "\n")
    else:
        edits.insert(root.end - 1, "\n(lib_symbols\n" + raw + ")\n")


def append(edits, raw):
    edits.insert(edits.doc.root.end - 1, "\n" + raw + "\n")


def plan_add_symbol(data, args, context):
    edits = Edits(data)
    uuid_check(edits.doc.root)
    for key in ("lib_id", "reference", "x_mm", "y_mm"):
        if key not in args:
            raise PcbAiError("invalid_arguments", "add_symbol preview requires " + key)
    reference = text(args["reference"], "Reference")
    if not re.fullmatch(r"#?[A-Za-z]+[0-9]+", reference):
        raise PcbAiError("invalid_arguments", "Use an annotated reference such as R1, U2 or #PWR1")
    info, add_cache = source_info(data, args["lib_id"])
    unit = args.get("unit", 1)
    active = pins(info, unit)
    existing = [r for r in context["references"] if r["reference"] == reference]
    if existing and any(r["unit"] == unit or r["lib_id"] != args["lib_id"] or
                        r["sheet_path"] not in {None, context["sheet_path"]} for r in existing):
        raise PcbAiError("duplicate_reference", "Reference/unit conflicts with a current project instance")
    at = location(edits.doc.root, args["x_mm"], args["y_mm"])
    rotation = args.get("rotation_deg", 0)
    if rotation not in {0, 90, 180, 270}:
        raise PcbAiError("invalid_arguments", "Schematic rotation must be 0, 90, 180 or 270")
    mirror = args.get("mirror")
    if mirror not in {None, "x", "y"}:
        raise PcbAiError("invalid_arguments", "Mirror must be x or y")
    props = info["properties"]
    value = text(args.get("value", props.get("Value", args["lib_id"].split(":")[1])), "Value")
    fp = args.get("footprint", props.get("Footprint", ""))
    if fp:
        identifier(fp)
    if existing and any(r["properties"].get("Value") != value or r["properties"].get("Footprint", "") != fp for r in existing):
        raise PcbAiError("ambiguous_reference", "All units of a component must have the same Value and Footprint")
    fields = dict(Reference=reference, Value=value, Footprint=fp, Datasheet=props.get("Datasheet", ""),
                  Description=props.get("Description", ""))
    field_text = []
    for i, (key, val) in enumerate(fields.items()):
        # Fixed deterministic readable field offsets, independent of installed library field placement.
        effects = "(effects (font (size 1.27 1.27))" + (" (hide yes)" if i > 1 else "") + ")"
        field_text.append(f"(property {quoted(key)} {quoted(val)} (at {fmt(at[0] + 2.54)} {fmt(at[1] + i * 2.54)} 0) {effects})")
    uid = str(uuid.uuid4())
    pin_text = "\n".join(f'(pin {quoted(p)} (uuid "{uuid.uuid4()}"))' for p in sorted({p["number"] for p in active}))
    mirror_text = f"(mirror {mirror})" if mirror else ""
    bom = "no" if reference.startswith("#") else "yes"
    raw = (f'(symbol (lib_id {quoted(args["lib_id"])}) (at {fmt(at[0])} {fmt(at[1])} {rotation}) '
           f'(unit {unit}) {mirror_text} (in_bom {bom}) (on_board {bom}) (dnp no) (uuid "{uid}")\n' +
           "\n".join(field_text) + "\n" + pin_text +
           f'\n(instances (project {quoted(context["project"])} (path {quoted(context["sheet_path"])} '
           f'(reference {quoted(reference)}) (unit {unit})))))')
    if add_cache:
        cache_insert(edits, info)
    append(edits, raw)
    changed = edits.result()
    uuid_check(_schematic(changed).root)
    return dict(data=changed, affected_references=[reference], symbol_uuid=uid, unit=unit, library_source=info["source"],
                definition_sha256=info["definition_sha256"], warnings=["Incremental construction can have ERC findings; inspect the measured report"])


def selected(data, reference, context, unit=None):
    matches = []
    for node in _schematic(data).root.all("symbol"):
        records = [r for r in _instances(node) if _in_project(r, context["project"], context["root_uuid"]) and
                   r["sheet_path"] in {None, context["sheet_path"]} and r["reference"] == reference and
                   (unit is None or r["unit"] == unit)]
        if len(records) > 1:
            raise PcbAiError("ambiguous_reference", "Duplicate reference/unit instance records")
        if records:
            if any(not _in_project(r, context["project"], context["root_uuid"]) or
                   r["sheet_path"] not in {None, context["sheet_path"]} for r in _instances(node)):
                raise PcbAiError("shared_sheet", "This stored symbol also belongs to another instance/project")
            matches.append((node, records[0]))
    if not matches:
        raise PcbAiError("unknown_reference", "Reference is absent on this project/sheet")
    if len({record["unit"] for _, record in matches}) != len(matches):
        raise PcbAiError("ambiguous_reference", "Reference/unit occurs more than once")
    return matches


def endpoint(data, specification, context):
    matches = []
    for node, instance in selected(data, specification["reference"], context, specification.get("unit")):
        lib = node.child("lib_name") or node.child("lib_id")
        if lib is None:
            raise PcbAiError("invalid_library", "Symbol has no library identifier")
        info = cached_info(data, lib.value())
        style = node.child("body_style") or node.child("convert")
        rotation = number(node.child("at").value(3, "0"))
        mirror = node.child("mirror")
        for pin in pins(info, instance["unit"], int(style.value()) if style else 1):
            if pin["number"] == specification["pin"]:
                at = place(pin["at"], point(node), rotation, mirror.value() if mirror else None)
                matches.append(dict(reference=instance["reference"], unit=instance["unit"], pin=pin["number"], at=at))
    if len(matches) != 1:
        raise PcbAiError("ambiguous_pin" if matches else "unknown_pin", "Use a unique literal pin number and unit")
    return matches[0]


def label_raw(name, at, kind="local", rotation=0):
    uid = str(uuid.uuid4())
    tag = "global_label" if kind == "global" else "label"
    shape = "(shape passive)" if kind == "global" else ""
    return (f'({tag} {quoted(name)} {shape} (at {fmt(at[0])} {fmt(at[1])} {rotation}) '
            f'(effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{uid}"))'), uid


def plan_labels(data, args, context, *, connect=False):
    edits = Edits(data)
    uuid_check(edits.doc.root)
    if "name" not in args:
        raise PcbAiError("invalid_arguments", "Preview requires a net name")
    name = text(args["name"], "Net name")
    kind = args.get("kind", "local")
    if kind not in {"local", "global"}:
        raise PcbAiError("invalid_arguments", "Only local/global labels are supported")
    rotation = args.get("rotation_deg", 0)
    if rotation not in {0, 90, 180, 270}:
        raise PcbAiError("invalid_arguments", "Label rotation must be cardinal")
    if connect:
        specs = args.get("endpoints", [])
        if not 2 <= len(specs) <= 64:
            raise PcbAiError("invalid_arguments", "Connect requires 2–64 explicit pin endpoints")
        endpoints = [endpoint(data, spec, context) for spec in specs]
        if len({(p["reference"], p["unit"], p["pin"]) for p in endpoints}) != len(endpoints):
            raise PcbAiError("invalid_arguments", "Duplicate pin endpoint")
        locations = [location(edits.doc.root, *e["at"]) for e in endpoints]
    else:
        if "x_mm" not in args or "y_mm" not in args:
            raise PcbAiError("invalid_arguments", "Label preview requires x_mm and y_mm")
        locations = [location(edits.doc.root, args["x_mm"], args["y_mm"])]
        endpoints = []
    ids = []
    for at in sorted(set(tuple(p) for p in locations)):
        raw, uid = label_raw(name, at, kind, rotation)
        append(edits, raw)
        ids.append(uid)
    return dict(data=edits.result(), net_name=name, label_uuids=ids, endpoints=endpoints,
                affected_references=sorted({e["reference"] for e in endpoints}),
                warnings=["Labels join every matching net name in their scope; review netlist and ERC"])


def plan_replace(data, args, context):
    for key in ("reference", "lib_id"):
        if key not in args:
            raise PcbAiError("invalid_arguments", "replace_part preview requires " + key)
    edits = Edits(data)
    uuid_check(edits.doc.root)
    matches = selected(data, args["reference"], context)
    if any(r["reference"] == args["reference"] and r["sheet_path"] not in {None, context["sheet_path"]}
           for r in context["references"]):
        raise PcbAiError("multi_document_component", "Replacement spans several sheets; a multi-file transaction is required")
    info, add_cache = source_info(data, args["lib_id"])
    for node, record in matches:
        old_lib = node.child("lib_name") or node.child("lib_id")
        old = cached_info(data, old_lib.value())
        style = node.child("body_style") or node.child("convert")
        style = int(style.value()) if style else 1
        def geometry(source, unit=record["unit"], body_style=style):
            return sorted((p["number"], *p["at"], p["rotation"], p["electrical_type"], p["shape"])
                          for p in pins(source, unit, body_style))
        if geometry(old) != geometry(info):
            raise PcbAiError("incompatible_pins", "Replacement changes pin identity, geometry or electrical type; wires were not moved")
        # Pin identity/geometry preserved in the local frame, hence under every rotation/mirror.
        for field in (node.child("lib_id"), node.child("lib_name")):
            if field:
                edits.atom(field.children[1], quoted(args["lib_id"]))
        fp = args.get("footprint", info["properties"].get("Footprint", ""))
        if fp:
            identifier(fp)
        for key, val in {"Value": text(args.get("value", info["properties"].get("Value", args["lib_id"].split(":")[1])), "Value"),
                         "Footprint": fp, "Datasheet": info["properties"].get("Datasheet", "")}.items():
            field = next((p for p in node.all("property") if p.value() == key), None)
            if field:
                edits.atom(field.children[2], quoted(val))
            elif val:
                raise PcbAiError("invalid_document", "Symbol has no editable " + key + " property")
    if add_cache:
        cache_insert(edits, info)
    return dict(data=edits.result(), affected_references=[args["reference"]], affected_units=[r["unit"] for _, r in matches],
                library_source=info["source"], definition_sha256=info["definition_sha256"], warnings=[])
