"""Bounded JSON/semantic preflight. Never writes project files or executes IR text."""
import difflib
import json
import math
from itertools import islice
from importlib.resources import files

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.exceptions import NoSuchResource

from pcbai.blocks.registry import expand
from pcbai.core.contract import PcbAiError
from pcbai.kicad.files import digest
from pcbai.ir.units import quantity, quantity_range, positive
from pcbai.parts.library import symbol, verify_part


def no_remote(uri):
    raise NoSuchResource(ref=uri)


SCHEMA = json.loads(files("pcbai.ir").joinpath("circuit.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA, registry=Registry(retrieve=no_remote))


def bounded_json(value):
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > 20000 or depth > 16:
            raise PcbAiError("invalid_ir", "IR exceeds node/depth limits")
        if isinstance(item, dict):
            if any(not isinstance(k, str) for k in item):
                raise PcbAiError("invalid_ir", "Object keys must be text")
            pending.extend((k, depth + 1) for k in item)
            pending.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            pending.extend((v, depth + 1) for v in item)
        elif isinstance(item, str):
            if len(item) > 4096 or any(ord(c) < 32 or 127 <= ord(c) <= 159 or 0xD800 <= ord(c) <= 0xDFFF for c in item):
                raise PcbAiError("invalid_ir", "IR text is too long or contains control characters")
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            try:
                if not math.isfinite(item):
                    raise PcbAiError("invalid_ir", "IR numbers must be finite")
            except OverflowError as exc:
                raise PcbAiError("invalid_ir", "IR number overflowed") from exc
        elif item is not None and not isinstance(item, bool):
            raise PcbAiError("invalid_ir", "IR must contain JSON data only")
    encoded = json.dumps(value, sort_keys=True, allow_nan=False, ensure_ascii=False).encode("utf-8")
    if len(encoded) > 1024 * 1024:
        raise PcbAiError("invalid_ir", "IR exceeds 1 MiB")
    return encoded


def validate_ir(ir):
    encoded = bounded_json(ir)
    errors = list(islice(VALIDATOR.iter_errors(ir), 30))
    if errors:
        findings = []
        for error in errors[:30]:
            suggestion = None
            if error.validator == "additionalProperties" and isinstance(error.instance, dict):
                known = error.schema.get("properties", {})
                unknown = set(error.instance) - set(known)
                suggestions = {key: difflib.get_close_matches(key, known, n=1) for key in sorted(unknown)}
                suggestion = {k: v[0] for k, v in suggestions.items() if v}
            findings.append(dict(path=list(error.path), code="schema", message=error.message, suggestion=suggestion))
        raise PcbAiError("invalid_ir", "Circuit IR does not match v1 schema", details=findings)
    return digest(encoded)


def invalid(code, message, path):
    raise PcbAiError(code, message, details={"path": path})


def plan(ir):
    ir_id = validate_ir(ir)
    requirements = dict(ir["requirements"])
    if "vin" in requirements:
        requirements["vin"] = quantity_range(requirements["vin"], "voltage")
    instances, components, endpoints, calculations, warnings = {}, [], {}, [], []
    inspected, pairs = {}, {}

    def inspect(part):
        key = part["symbol"]
        if key not in inspected:
            inspected[key] = symbol(key)
        info = inspected[key]
        unit = int(part.get("unit", 1))
        if unit not in info["units"]:
            invalid("unknown_unit", f"Unavailable unit {unit} for {key}", ["parts", part["id"], "unit"])
        active = [p for p in info["pins"] if p["unit"] in {0, unit}]
        footprint = part.get("footprint", info["properties"].get("Footprint", ""))
        if footprint and (key, footprint) not in pairs:
            pairs[key, footprint] = verify_part(key, footprint)
        pair = pairs.get((key, footprint))
        if pair and pair["symbol_library_sha256"] != info["library_sha256"]:
            invalid("stale_library", "Symbol library changed during planning", ["parts", part["id"]])
        if pair and not pair["pin_pad_match"]:
            invalid("incompatible_pins", f"Symbol/footprint pins do not match for {part['id']}", ["parts", part["id"]])
        return dict(part, footprint=footprint, unit=unit, pins=active, verified=False, stock_verified=False,
                    symbol_library_sha256=info["library_sha256"], pin_pad_match=pair["pin_pad_match"] if pair else None,
                    footprint_sha256=pair["footprint_sha256"] if pair else None)

    for index, entry in enumerate([*ir["blocks"], *ir["parts"]]):
        id = entry["id"]
        if id in instances:
            invalid("duplicate_id", "Each part/block ID must be unique: " + id, ["instances", index])
        instances[id] = entry
    for entry in ir["blocks"]:
        expanded = expand(entry["block"], entry["params"])
        id = entry["id"]
        calculations.append(dict(block_id=id, **expanded["calculation"]))
        warnings.extend(id + ": " + w for w in expanded["warnings"])
        for part in expanded["parts"]:
            components.append(inspect(dict(part, id=id + "/" + part["id"], block_id=id)))
        for port, pins in expanded["port_pins"].items():
            endpoints[id + "." + port] = dict(kind=expanded["ports"][port], pins=[dict(part=id + "/" + p["part"], pin=p["pin"]) for p in pins])
    for entry in ir["parts"]:
        component = inspect(entry)
        components.append(component)
        for pin in component["pins"]:
            key = entry["id"] + "." + pin["number"]
            endpoints.setdefault(key, dict(kind=pin["electrical_type"], pins=[dict(part=entry["id"], pin=pin["number"])]))

    if len(components) > 150:
        invalid("circuit_too_large", "Expanded circuit exceeds 150 components", ["blocks"])
    # Resolve recipe pin maps against the inspected symbols as well as free parts.
    physical_pins = {p["id"]: {pin["number"] for pin in p["pins"]} for p in components}
    for name, endpoint in endpoints.items():
        for pin in endpoint["pins"]:
            if pin["pin"] not in physical_pins[pin["part"]]:
                invalid("unknown_endpoint", "Recipe refers to an unavailable literal pin", ["blocks", name])

    rails = {}
    for name, rail in ir["rails"].items():
        actual = dict(rail, verified=False, source_authority="caller_declared")
        if rail.get("ground"):
            if "voltage" in rail and quantity(rail["voltage"], "voltage") != 0:
                invalid("invalid_rail", "Ground rail voltage must be zero", ["rails", name])
            actual["voltage_v"] = 0
        else:
            if rail["from"] not in endpoints:
                invalid("unknown_endpoint", "Rail source must be a known part pin/block port", ["rails", name, "from"])
            if endpoints[rail["from"]]["kind"] not in {"power_out"}:
                invalid("invalid_rail_source", "Rail source is not a power output", ["rails", name, "from"])
            if "voltage" in rail:
                actual["voltage_v"] = quantity(rail["voltage"], "voltage")
        if "current_limit" in rail:
            actual["current_limit_a"] = positive(rail["current_limit"], "current")
        rails[name] = actual
        endpoints["@" + name] = dict(kind="ground" if rail.get("ground") else "power_out", pins=[])

    parents = {name: name for name in endpoints}
    def find(name):
        while parents[name] != name:
            parents[name] = parents[parents[name]]
            name = parents[name]
        return name
    def join(a, b):
        a, b = find(a), find(b)
        if a != b:
            parents[max(a, b)] = min(a, b)
    # Ports that refer to the same physical pin (INPUT/OUT debounce) are aliases.
    pin_owners = {}
    for name, endpoint in endpoints.items():
        for pin in endpoint["pins"]:
            key = (pin["part"], pin["pin"])
            if key in pin_owners:
                join(name, pin_owners[key])
            pin_owners[key] = name
    for name, rail in rails.items():
        if "from" in rail:
            join("@" + name, rail["from"])
    for index, connection in enumerate(ir["connections"]):
        if len(set(connection)) != len(connection):
            invalid("duplicate_endpoint", "A connection contains duplicate endpoints", ["connections", index])
        for endpoint in connection:
            if endpoint not in endpoints:
                invalid("unknown_endpoint", "Unknown literal pin/port/rail: " + endpoint, ["connections", index])
        for other in connection[1:]:
            join(connection[0], other)
    groups = {}
    for name, endpoint in endpoints.items():
        group = groups.setdefault(find(name), dict(endpoints=[], pins=[], rails=[]))
        group["endpoints"].append(name)
        group["pins"].extend(endpoint["pins"])
        if name.startswith("@"):
            group["rails"].append(name[1:])
    questions = []
    for group in groups.values():
        group["pins"] = [dict(part=p, pin=n) for p, n in sorted({(p["part"], p["pin"]) for p in group["pins"]})]
        if len(group["rails"]) > 1:
            invalid("rail_conflict", "A connection merges distinct rails: " + ", ".join(group["rails"]), ["connections"])
        if not group["rails"] and any(endpoints[e]["kind"] == "ground" for e in group["endpoints"]):
            questions.append("Connect the ground ports to an explicit @ground rail: " + ", ".join(group["endpoints"]))
        if len(group["pins"]) < 2 and not group["rails"]:
            warnings.append("Single-pin/unmapped external interface: " + ", ".join(group["endpoints"]))
    for index, constraint in enumerate(ir.get("constraints", [])):
        owner = constraint.get("around") or constraint.get("edge", "").split(".")[0]
        if owner not in instances:
            invalid("unknown_constraint_owner", "Constraint refers to an unknown part/block", ["constraints", index])
        if "edge" in constraint:
            ref = constraint["edge"]
            component_ids = {p["id"] for p in components}
            if ref != owner and ref.replace(".", "/", 1) not in component_ids:
                invalid("unknown_constraint_owner", "Edge constraint must name a part or generated block component", ["constraints", index, "edge"])
    warnings.append("Stock, datasheets, voltage-domain/AF checks and physical validation are not available in this preflight")
    if ir.get("constraints"):
        warnings.append("Placement/keepout constraints are validated as references only; not enforced")
    return dict(ir_id=ir_id, ir_version=1, requirements=requirements, components=components, rails=rails,
                nets=list(groups.values()), calculations=calculations, questions=questions, warnings=warnings,
                stages=dict(schema="passed", references="passed", calculation="passed", electrical="incomplete"),
                ready_to_apply=False, production_verified=False, assumptions=ir.get("assumptions", []),
                limitations=["No schematic files written", "No stock/vendor/AF facts inferred", "No multi-file apply or incremental UUID mapping"])
