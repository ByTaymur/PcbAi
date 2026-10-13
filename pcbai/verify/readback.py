"""Freeze user intent against the original, then measure freshly read saved bytes."""
import copy
import json
import math

from pcbai.blocks.registry import expand
from pcbai.blocks.schematic import reserve
from pcbai.core.contract import PcbAiError
from pcbai.kicad.files import digest, within
from pcbai.sch.model import footprints, properties, symbols
from pcbai.sexpr import Document
from pcbai.verify.findings import normalize_findings


def uuid(node):
    child = node.child("uuid") or node.child("tstamp")
    return child.value() if child else None


def position(node):
    at = node.child("at")
    return [float(n.atom) for n in at.children[1:]] if at else []


def tracks(data):
    root = Document(data).root
    return {uuid(n): dict(width=float(n.child("width").value()), net=n.child("net").value())
            for kind in ("segment", "arc") for n in root.all(kind)}


def counts(data):
    root = Document(data).root
    return {kind: len(root.all(kind)) for kind in ("segment", "arc", "via", "footprint")}


def freeze(name, args, original, impact, candidate, context=None, netlist=None, checkpoint_bytes=None):
    """UUIDs may be allocated by the planner; requested semantics never come from candidate bytes."""
    intent = dict(tool=name, args=copy.deepcopy(args))
    if name == "set_value":
        records = symbols(original)
        selected = {s["uuid"] for s in symbols(original, context["project"], context["root_uuid"])
                    if s["reference"] == args["reference"]}
        def component(s):
            parts = (s["sheet_path"] or "").split("/")
            return s["project"], parts[1] if len(parts) > 1 else None, s["reference"]
        # Physical shared units propagate through the original instance identities.
        while True:
            keys = {component(s) for s in records if s["uuid"] in selected}
            enlarged = selected | {s["uuid"] for s in records if component(s) in keys}
            if enlarged == selected:
                break
            selected = enlarged
        intent["symbols"] = [dict(uuid=s["uuid"], value=args["value"]) for s in symbols(original)
                             if s["uuid"] in selected]
    elif name == "add_symbol":
        intent["symbols"] = [dict(uuid=impact["symbol_uuid"], reference=args["reference"],
            lib_id=args["lib_id"], at=[args["x_mm"], args["y_mm"], args.get("rotation_deg", 0)],
            **({"value": args["value"]} if "value" in args else {}),
            **({"footprint": args["footprint"]} if "footprint" in args else {}))]
    elif name == "replace_part":
        intent["symbols"] = [dict(uuid=s["uuid"], reference=args["reference"], lib_id=args["lib_id"], at=s["at"],
                                  **({"value": args["value"]} if "value" in args else {}))
                             for s in symbols(original, context["project"], context["root_uuid"])
                             if s["reference"] == args["reference"]]
    elif name == "add_label":
        intent["labels"] = [dict(uuid=u, name=args["name"], at=[args["x_mm"], args["y_mm"]],
                                kind="global_label" if args.get("kind") == "global" else "label")
                            for u in impact["label_uuids"]]
    elif name == "connect":
        # Preserve the old members of each requested pin's net as well as requested pins.
        wanted = {(p["reference"], p["pin"]) for p in args["endpoints"]}
        for p in tuple(wanted):
            old = netlist["pins"].get(p)
            wanted.update((m["reference"], m["pin"]) for m in netlist["members"].get(old, []))
        sheet_tail = "/".join(context["sheet_path"].strip("/").split("/")[1:])
        pages = [p for p in netlist["pages"] if p["tstamps"].strip("/") == sheet_tail]
        if len(pages) != 1:
            raise PcbAiError("ambiguous_intent", "Native sheet scope could not be resolved for connection intent")
        existing_name = args["name"] if args.get("kind") == "global" else pages[0]["names"] + args["name"]
        wanted.update((m["reference"], m["pin"]) for m in netlist["members"].get(existing_name, []))
        preview_members = {(m["reference"], m["pin"]) for m in impact["net_members"]}
        if preview_members != wanted:
            raise PcbAiError("ambiguous_intent", "Existing label aliases add members outside the independently resolved connection intent")
        intent["net_groups"] = [sorted(wanted)]
        intent["net_exact"] = True
        from pcbai.sch.edit import endpoint
        intent["label_anchors"] = [endpoint(original, p, context)["at"] for p in args["endpoints"]]
    elif name == "add_block":
        recipe = expand(args["block"], args["params"])
        refs = reserve(recipe["parts"], context["references"])
        intent["net_groups"] = sorted({tuple(sorted((refs[p["part"]], p["pin"]) for p in pins))
                                       for pins in recipe["port_pins"].values()})
        aliases = {}
        for port, pins in recipe["port_pins"].items():
            group = tuple(sorted((refs[p["part"]], p["pin"]) for p in pins))
            aliases.setdefault(group, "PcbAi_" + args["instance"] + "_" + port)
        intent["net_labels"] = [aliases[group] for group in intent["net_groups"]]
        intent["net_exact"] = True
        intent["symbols"] = [dict(uuid=u, reference=refs[p["id"]], lib_id=p["symbol"], value=p["value"],
            at=[args["x_mm"] + i * 50.8, args["y_mm"], 0])
            for i, (u, p) in enumerate(zip(impact["symbol_uuids"], recipe["parts"], strict=True))]
    elif name == "move_footprint":
        old = next(f for f in footprints(original) if f["Reference"] == args["reference"])
        angle = old["at"][2] if len(old["at"]) > 2 else 0
        side = args.get("side", "back" if old["layer"] == "B.Cu" else "front")
        # The writer mirrors the board-absolute angle on a side change.
        rotation = args.get("rotation_deg", (180 - angle) if
            side != ("back" if old["layer"] == "B.Cu" else "front") else angle) % 360
        intent["footprint"] = dict(reference=args["reference"], at=[args.get("x_mm", old["at"][0]),
            args.get("y_mm", old["at"][1]), rotation], layer="B.Cu" if side == "back" else "F.Cu")
    elif name == "set_track_width":
        old = tracks(original)
        chosen = set(args.get("uuids", [])) if args.get("uuids") else {
            u for u, t in old.items() if t["net"] == args["net"] or
            any(n.value() == t["net"] and n.value(2) == args["net"] for n in Document(original).root.all("net"))}
        intent["widths"] = {u: float(args["width_mm"]) if u in chosen else t["width"] for u, t in old.items()}
    elif name == "add_zone":
        intent["zone"] = dict(uuid=impact["zone_uuid"], net=args["net"], layer=args["layer"], points=args["points_mm"])
    elif name == "set_netclass":
        intent["netclass"] = dict(name=args["netclass"], values={key: args[key] for key in
            ("clearance_mm", "track_width_mm", "via_diameter_mm", "via_drill_mm") if key in args},
            patterns=args.get("patterns", []))
    elif name in {"autoroute", "autoplace"}:
        intent["counts"] = counts(candidate)
    elif name == "restore_checkpoint":
        intent["checkpoint_sha256"] = digest(checkpoint_bytes)
    return copy.deepcopy(intent)


def measure(path, expected_sha256, intent, native_netlist=None, project_root=None):
    checked, mismatches = [], []
    def compare(key, actual, expected):
        checked.append(key)
        def equal(a, b):
            if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
                return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b, strict=True))
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                return math.isfinite(a) and math.isfinite(b) and abs(a - b) <= .001
            return a == b
        if not equal(actual, expected):
            mismatches.append(dict(check=key, expected=expected, actual=actual))
    try:
        def read_saved():
            safe = within(project_root, str(path.relative_to(project_root))) if project_root is not None else path
            return safe.read_bytes()
        saved = read_saved()
        compare("sha256", digest(saved), expected_sha256)
        if "checkpoint_sha256" in intent:
            compare("checkpoint_sha256", digest(saved), intent["checkpoint_sha256"])
        if intent["tool"] == "set_netclass":
            project = json.loads(saved)
            spec = intent["netclass"]
            classes = [c for c in project["net_settings"]["classes"] if c["name"] == spec["name"]]
            compare("netclass_count", len(classes), 1)
            if len(classes) == 1:
                for key, value in spec["values"].items():
                    compare(key, classes[0].get(key.removesuffix("_mm")), float(value))
            for pattern in spec["patterns"]:
                compare("pattern:" + pattern, [p["netclass"] for p in project["net_settings"].get("netclass_patterns", [])
                                               if p["pattern"] == pattern], [spec["name"]])
        elif intent["tool"] != "restore_checkpoint":
            root = Document(saved).root
            for spec in intent.get("symbols", []):
                matches = [n for n in root.all("symbol") if uuid(n) == spec["uuid"]]
                compare("symbol:" + str(spec["uuid"]), len(matches), 1)
                if len(matches) != 1:
                    continue
                node = matches[0]
                props = properties(node)
                for key in ("reference", "value", "footprint"):
                    if key in spec:
                        compare(key + ":" + spec["uuid"], props.get(key.title()), spec[key])
                if "lib_id" in spec:
                    compare("lib_id:" + spec["uuid"], node.child("lib_id").value(), spec["lib_id"])
                if "at" in spec:
                    compare("symbol_at:" + spec["uuid"], position(node), spec["at"])
            for spec in intent.get("labels", []):
                matches = [n for n in root.all(spec["kind"]) if uuid(n) == spec["uuid"]]
                compare("label:" + spec["uuid"], len(matches), 1)
                if len(matches) == 1:
                    compare("label_name", matches[0].value(), spec["name"])
                    compare("label_at", position(matches[0])[:2], spec["at"])
            if "label_anchors" in intent:
                tag = "global_label" if intent["args"].get("kind") == "global" else "label"
                for at in intent["label_anchors"]:
                    compare("connection_label", any(n.value() == intent["args"]["name"] and
                            all(abs(a - b) <= .001 for a, b in zip(position(n)[:2], at, strict=True))
                            for n in root.all(tag)), True)
            if "footprint" in intent:
                spec = intent["footprint"]
                matches = [f for f in footprints(saved) if f["Reference"] == spec["reference"]]
                compare("footprint_count", len(matches), 1)
                if len(matches) == 1:
                    at = matches[0]["at"]
                    compare("footprint_at", at[:2] + [(at[2] if len(at) > 2 else 0) % 360], spec["at"])
                    compare("footprint_layer", matches[0]["layer"], spec["layer"])
            if "widths" in intent:
                actual = tracks(saved)
                compare("track_uuids", sorted(actual), sorted(intent["widths"]))
                for u, width in intent["widths"].items():
                    compare("width:" + str(u), actual.get(u, {}).get("width"), width)
            if "zone" in intent:
                spec = intent["zone"]
                matches = [n for n in root.all("zone") if uuid(n) == spec["uuid"]]
                compare("zone_count", len(matches), 1)
                if len(matches) == 1:
                    node = matches[0]
                    net = node.child("net_name")
                    compare("zone_net", net.value() if net else node.child("net").value(), spec["net"])
                    compare("zone_layer", node.child("layer").value(), spec["layer"])
                    compare("zone_points", [[float(p.value()), float(p.value(2))]
                        for p in node.child("polygon").child("pts").all("xy")], spec["points"])
            if "counts" in intent:
                for kind, total in intent["counts"].items():
                    compare(kind + "_count", len(root.all(kind)), total)
            if "net_groups" in intent:
                parsed = native_netlist()
                used = set()
                for index, group in enumerate(intent["net_groups"]):
                    names = {parsed["pins"].get(tuple(p)) for p in group}
                    compare(f"net_group:{index}", len(names) == 1 and None not in names, True)
                    if len(names) == 1 and None not in names:
                        net = next(iter(names))
                        if "net_labels" in intent:
                            compare(f"net_label:{index}", net.rsplit("/", 1)[-1], intent["net_labels"][index])
                        compare(f"distinct_net:{index}", net not in used, True)
                        used.add(net)
                        members = {(p["reference"], p["pin"]) for p in parsed["members"][net]}
                        expected = {tuple(p) for p in group}
                        compare(f"net_members:{index}", members == expected if intent["net_exact"]
                                else expected <= members, True)
        # No measurement can attest to a revision that changed during measurement.
        compare("stable_read", digest(read_saved()), digest(saved))
    except Exception as exc:
        checked.append("readback_available")
        mismatches.append(dict(check="readback_available", error_code=getattr(exc, "code", "readback_failed")))
    findings = normalize_findings([dict(type="readback_mismatch", severity="error", group=m["check"],
        description="Saved document does not satisfy " + m["check"], items=[]) for m in mismatches], "readback")
    return dict(checked=checked, mismatches=mismatches, findings=findings)
