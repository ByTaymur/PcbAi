"""Independent net naming, membership partition and multiplicity calibration."""
from collections import Counter, defaultdict

from pcbai.core.contract import PcbAiError
from pcbai.kicad.cli import snapshot
from pcbai.kicad.files import revision, within
from pcbai.kicad.exports import board_stats
from pcbai.sch.scene import parse_netlist
from pcbai.sch_render import export_netlist
from pcbai.sexpr import Document
from pcbai.verify.findings import normalize_findings
from pcbai.verify.manifest import entry, verification

DEPENDENCIES = {
    "topology": {"components", "sheet_instances", "net_count", "net_partitions", "net_names"},
    "pin_count_current": {"components", "sheet_instances", "net_count", "net_partitions", "net_names", "net_multiplicity"},
    "pcb_geometry": {"footprints", "pads", "vias", "segments"},
}


def normalized_name(name, pages):
    """Only explicit native UUID→sheet path mappings and the leading slash are removed."""
    candidates = defaultdict(set)
    for page in pages:
        stamp = (page.get("tstamps") or "").strip("/")
        path = (page.get("names") or "/").strip("/")
        if stamp:
            candidates[stamp].add(path)
            if "/" in stamp:
                candidates[stamp.split("/", 1)[1]].add(path)
    plain = name[1:] if name.startswith("/") else name
    for stamp in sorted(candidates, key=len, reverse=True):
        if plain.startswith(stamp + "/") and len(candidates[stamp]) == 1:
            return "/".join(filter(None, [next(iter(candidates[stamp])), plain[len(stamp) + 1:]]))
    return plain


def unnamed(name):
    # Pin names themselves can contain '/', e.g. unconnected-(U9-P/A3-Pad6).
    plain = name.lstrip("/")
    return plain.startswith(("Net-(", "unconnected-", "__unnamed_")) or any(
        part.startswith(("Net-(", "unconnected-", "__unnamed_")) for part in plain.split("/"))


def members(model):
    nets = model.get("nets")
    if not isinstance(nets, dict):
        raise PcbAiError("invalid_model", "Model nets must be an object")
    output = {}
    for name, pins in nets.items():
        if not isinstance(name, str) or not isinstance(pins, list):
            raise PcbAiError("invalid_model", "Malformed net members")
        if any(not isinstance(pair, (list, tuple)) or len(pair) != 2
               or any(not isinstance(value, str) or not value for value in pair) for pair in pins):
            raise PcbAiError("invalid_model", "Net members need reference/pin text pairs")
        output[name] = [tuple(pair) for pair in pins]
    return output


def calibrate(native, external):
    expected, actual = members(native), members(external)
    findings, checks = [], []
    def compare(identifier, match, rule, description, missing=False):
        status = "skipped" if missing else "ran"
        row = entry(identifier, status=status, reason="model_field_missing" if missing else None,
                    limit_id="L-EXTERNAL-MODEL-CALIBRATION" if missing else None, tool="calibrate")
        row["matches"] = bool(match) if not missing else None
        checks.append(row)
        if not match and not missing:
            findings.append(dict(type=rule, severity="error", description=description, items=[], group=identifier))
    for field in ("components", "sheet_instances", "footprints", "pads", "vias", "segments"):
        a, b = native.get(field), external.get(field)
        if field == "components" and a is not None and b is not None:
            if not isinstance(a, list) or not isinstance(b, list) or any(not isinstance(v, str) for v in a + b):
                raise PcbAiError("invalid_model", "Component references must be text lists")
            a, b = set(a), set(b)
        elif a is not None and b is not None and (type(a) is not int or type(b) is not int or min(a, b) < 0):
            raise PcbAiError("invalid_model", "Model counts must be nonnegative integers")
        compare(field, a == b, "count_mismatch", f"{field}: native and external differ", missing=a is None or b is None)
    compare("net_count", len(expected) == len(actual), "count_mismatch", "Net counts differ")
    partition_a = Counter(frozenset(pins) for pins in expected.values())
    partition_b = Counter(frozenset(pins) for pins in actual.values())
    compare("net_partitions", partition_a == partition_b, "net_members_mismatch", "Member partitions differ")
    pages = native.get("pages", [])
    names_a, names_b = defaultdict(list), defaultdict(list)
    for target, nets in ((names_a, expected), (names_b, actual)):
        for name, pins in nets.items():
            if not unnamed(name):
                target[normalized_name(name, pages)].append(frozenset(pins))
    names_ok = {k: Counter(v) for k, v in names_a.items()} == {k: Counter(v) for k, v in names_b.items()}
    compare("net_names", names_ok, "net_name_member_swap", "Named nets map to different members")
    # Preserve one finding per bad named net, including the two-net swap fixture.
    if not names_ok:
        findings.pop()
        for name in sorted(set(names_a) | set(names_b)):
            if Counter(names_a[name]) != Counter(names_b[name]):
                findings.append(dict(type="net_name_member_swap", severity="error", group="net_names",
                                     description=f"Named net {name} maps to different members", items=[dict(net=name)]))
    multiplicity_a = Counter(tuple(sorted(pins)) for pins in expected.values())
    multiplicity_b = Counter(tuple(sorted(pins)) for pins in actual.values())
    compare("net_multiplicity", multiplicity_a == multiplicity_b, "pin_multiplicity", "Pin multiplicities differ")
    if partition_a == partition_b and multiplicity_a != multiplicity_b:
        findings.pop()
        remaining = multiplicity_a.copy()
        for name, pins in sorted(actual.items()):
            signature = tuple(sorted(pins))
            if remaining[signature]:
                remaining[signature] -= 1
            else:
                findings.append(dict(type="pin_multiplicity", severity="error", group="net_multiplicity",
                                     description=f"Pin multiplicity differs for {name}", items=[dict(net=name)]))
    bad = {row["check_id"] for row in checks if row["status"] != "ran" or not row["matches"]}
    detectors = []
    for group, dependencies in DEPENDENCIES.items():
        blocked = bool(dependencies & bad)
        detectors.append(entry(group, status="skipped" if blocked else "ran",
            reason="calibration_failed" if blocked else None,
            limit_id="L-KH-PIN-MULTIPLICITY" if blocked and dependencies & bad == {"net_multiplicity"}
            else "L-EXTERNAL-MODEL-CALIBRATION" if blocked else None, tool="calibration_gate"))
        detectors[-1]["status"] = "skipped" if blocked else "not_applicable"
        detectors[-1]["reason"] = "calibration_failed" if blocked else "calibrated_not_executed"
    normalized = normalize_findings(findings, "calibration")
    return dict(verified=verification(checks, normalized), findings=normalized, checks_run=checks,
                detector_gates=detectors, calibrated=not bad)


def native_model(root, schematic, pcb=None):
    """KiCad XML and CLI statistics; saved geometry supplies CLI-unavailable segment count."""
    initial = revision(root)
    with snapshot(root, initial) as copy:
        parsed = parse_netlist(export_netlist(copy, schematic, copy / "native-calibration.xml"))
        model = dict(components=sorted(parsed["components"]), sheet_instances=len(parsed["pages"]),
                     pages=parsed["pages"], nets={name: [[pin["reference"], pin["pin"]] for pin in pins]
                                                for name, pins in parsed["members"].items()}, revision=initial)
        if pcb:
            stats = board_stats(copy, pcb, None)
            board = Document(within(copy, pcb).read_bytes()).root
            model.update(footprints=stats["components"]["total"]["total"], pads=sum(stats["pads"].values()),
                         vias=sum(stats["vias"].values()), segments=len(board.all("segment")) + len(board.all("arc")))
            model["count_sources"] = dict(footprints="kicad-cli", pads="kicad-cli", vias="kicad-cli", segments="saved_geometry")
        if revision(root) != initial:
            raise PcbAiError("stale_revision", "Project changed during calibration")
        return model
