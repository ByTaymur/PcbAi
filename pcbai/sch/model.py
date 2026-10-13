import uuid

from pcbai.core.contract import PcbAiError
from pcbai.sexpr import Document


def canonical_id(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        return value


def canonical_path(value):
    return "/".join(canonical_id(part) for part in value.split("/")) if value is not None else None


def properties(node):
    answer = {}
    for prop in node.all("property"):
        key = prop.value()
        if key in {"Reference", "Value"} and key in answer:
            raise PcbAiError("invalid_document", f"Duplicate {key} property")
        answer[key] = prop.value(2)
    return answer


def position(node):
    at = node.child("at")
    return [float(n.atom) for n in at.children[1:]] if at else None


def _schematic(data):
    doc = Document(data)
    if doc.root.name != "kicad_sch":
        raise PcbAiError("invalid_document", "Expected a KiCad schematic")
    return doc


def _instances(node):
    container = node.child("instances")
    if container is None:
        unit = node.child("unit")
        return [dict(project=None, sheet_path=None, reference=properties(node).get("Reference"),
                     unit=int(unit.value()) if unit else 1)]
    records = []
    for project in container.all("project"):
        for path in project.all("path"):
            reference, unit = path.child("reference"), path.child("unit")
            if project.value() is None or not path.value() or reference is None or not reference.value() or unit is None:
                raise PcbAiError("invalid_document", "Incomplete symbol instance record")
            try:
                number = int(unit.value())
                if number < 1:
                    raise ValueError()
            except (TypeError, ValueError) as exc:
                raise PcbAiError("invalid_document", "Invalid symbol instance unit") from exc
            records.append(dict(project=project.value(), sheet_path=canonical_path(path.value()),
                                reference=reference.value(), unit=number))
    if not records:
        raise PcbAiError("invalid_document", "Symbol instances contain no usable paths")
    return records


def _in_project(instance, project, root_uuid):
    if instance["project"] is None:
        return True
    if root_uuid is not None and canonical_path(instance["sheet_path"]).split("/")[1:2] != [canonical_id(root_uuid)]:
        return False
    return project is None or instance["project"] == project or (instance["project"] == "" and root_uuid is not None)


def _component_key(instance):
    path = instance["sheet_path"]
    return instance["project"], path.split("/")[1] if path and path.startswith("/") else None, instance["reference"]


def symbols(data, project=None, root_uuid=None):
    answer = []
    for node in _schematic(data).root.all("symbol"):
        props = properties(node)
        for instance in _instances(node):
            if not _in_project(instance, project, root_uuid):
                continue
            answer.append({**props, "Reference": instance["reference"], "properties": props,
                           "property_reference": props.get("Reference"),
                           "uuid": node.child("uuid").value() if node.child("uuid") else None,
                           "lib_id": node.child("lib_id").value() if node.child("lib_id") else None,
                           "at": position(node), "trusted": False, **instance})
    return answer


def footprints(data):
    doc = Document(data)
    if doc.root.name != "kicad_pcb":
        raise PcbAiError("invalid_document", "Expected a KiCad PCB")
    answer = []
    for node in doc.root.all("footprint"):
        props = properties(node)
        # Older boards use fp_text instead of properties.
        for text in node.all("fp_text"):
            if text.value() in {"reference", "value"}:
                props.setdefault(text.value().title(), text.value(2))
        answer.append(dict(props, footprint=node.value(), at=position(node),
                           layer=node.child("layer").value() if node.child("layer") else None,
                           trusted=False))
    return answer


def plan_value_edit(data, reference, value, project=None, root_uuid=None):
    if not isinstance(value, str) or any(ord(c) < 32 or 127 <= ord(c) <= 159 or 0xD800 <= ord(c) <= 0xDFFF
                                         for c in value):
        raise PcbAiError("invalid_arguments", "Value must not contain control characters or Unicode surrogates")
    doc = _schematic(data)
    entries = [(node, _instances(node)) for node in doc.root.all("symbol")]
    selected = {i for i, (_, records) in enumerate(entries)
                if any(r["reference"] == reference and _in_project(r, project, root_uuid)
                       for r in records)}
    if not selected:
        raise PcbAiError("unknown_reference", f"Symbol {reference} not found on this sheet")
    # A shared sheet can contain several units of each component. Follow the reference
    # connections until all units of every affected instance are included.
    while True:
        keys = {_component_key(r) for i in selected for r in entries[i][1]}
        expanded = {i for i, (_, records) in enumerate(entries)
                    if any(_component_key(r) in keys for r in records)}
        if expanded == selected:
            break
        selected = expanded
    edits = []
    old = set()
    affected = []
    seen_units = set()
    for i in sorted(selected):
        symbol, records = entries[i]
        for record in records:
            key = (*_component_key(record), record["unit"])
            if key in seen_units:
                raise PcbAiError("ambiguous_reference", "Reference/unit occurs in more than one instance")
            seen_units.add(key)
            affected.append(dict(record, uuid=symbol.child("uuid").value() if symbol.child("uuid") else None))
        field = next((p for p in symbol.all("property") if p.value() == "Value"), None)
        if field is None or len(field.children) < 3:
            raise PcbAiError("invalid_document", "Symbol has no editable Value property")
        old.add(field.value(2))
        edits.append(field.children[2])
    if len(old) != 1:
        raise PcbAiError("ambiguous_reference", "Units of this reference have different values")
    for node in sorted(edits, key=lambda n: n.start, reverse=True):
        data = Document(data).replace_string(node, value)
    references = sorted({r["reference"] for r in affected})
    shared = len({(r["project"], r["sheet_path"], r["reference"]) for r in affected}) > 1
    return dict(data=data, old_value=next(iter(old)), affected_references=references, affected_instances=affected,
                warnings=["Shared schematic file: changing Value affects every listed instance"]
                if shared else [])


def edit_value(data, reference, value, project=None, root_uuid=None):
    edit = plan_value_edit(data, reference, value, project, root_uuid)
    return edit["data"], edit["old_value"]
