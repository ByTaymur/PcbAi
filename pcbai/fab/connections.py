"""Three authorities kept separate: artwork geometry, PCB test netlist, schematic."""
import tempfile
import time
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli, run
from pcbai.fab.gerber import parse as parse_gerber, islands
from pcbai.fab.ipc356 import parse as parse_ipc
from pcbai.kicad.board import summary
from pcbai.kicad.cli import snapshot
from pcbai.kicad.exports import gerber_layer
from pcbai.kicad.files import digest, within
from pcbai.sch.scene import parse_netlist
from pcbai.sch_render import export_netlist
from pcbai.verify.findings import normalize_findings
from pcbai.verify.manifest import entry, verification


def schematic_authority(raw):
    native = parse_netlist(raw)
    xml = ET.fromstring(raw)
    refs, membership, net_codes, net_names = set(), {}, set(), set()
    for component in xml.iter("comp"):
        ref = component.get("ref")
        if not ref or ref.casefold() in refs:
            raise PcbAiError("invalid_report", "Native schematic component identity is ambiguous")
        refs.add(ref.casefold())
    for net in xml.iter("net"):
        name, code = net.get("name"), net.get("code")
        if not name or name in net_names or not code or not re.fullmatch(r"0|[1-9][0-9]*", code) or code in net_codes:
            raise PcbAiError("invalid_report", "Native schematic net identity is missing or repeated")
        net_names.add(name)
        net_codes.add(code)
        for node in net.iter("node"):
            key = (node.get("ref"), node.get("pin"))
            if not all(key) or key[0] not in native["components"] or key in membership:
                raise PcbAiError("invalid_report", "Native schematic pin membership is missing or repeated")
            membership[key] = net.get("name")
    return native


def reconcile(layers, ipc, native):
    """IPC coordinates must register to same-identity artwork pads; never guess offsets."""
    findings, checks, groups = [], [], defaultdict(list)
    expected = native["pins"]
    if not ipc["points"] or not expected:
        return [], [entry("pad_registration", status="skipped", reason="empty_pin_authority")], []
    registered = {}
    artwork_counts = Counter(shape["pin"] for layer in layers.values() for shape in layer["shapes"] if shape["pin"])
    for point in ipc["points"]:
        layer = layers.get(point["layer"])
        key = (point["reference"], point["pin"])
        if layer is None:
            checks.append(entry("pad_registration:" + ".".join(key), status="skipped", reason="copper_layer_unavailable"))
            continue
        choices = [(index, shape) for index, shape in enumerate(layer["shapes"]) if shape["pin"] == key]
        tolerance = ipc["quantum_mm"]/2 + layer["coordinate_quantum_mm"]
        matches = [(index, shape) for index, shape in choices
                   if abs(shape["center_mm"][0]-point["x_mm"]) <= tolerance
                   and abs(shape["center_mm"][1]-point["y_mm"]) <= tolerance]
        if artwork_counts[key] != 1 or len(matches) != 1 or key not in expected:
            checks.append(entry("pad_registration:" + ".".join(key), status="skipped",
                                reason="missing_ambiguous_or_unregistered_pad"))
            continue
        index, shape = matches[0]
        registered[key] = dict(point, island=(point["layer"], layer["islands"][index]),
                               schematic_net=expected[key], position_mm=list(shape["center_mm"]))
        groups[registered[key]["island"]].append(registered[key])
    missing = set(expected) - registered.keys()
    checks.append(entry("pad_registration", status="skipped" if missing else "ran",
                        reason="schematic_pins_not_registered" if missing else None))
    artwork_keys = {shape["pin"] for layer in layers.values() for shape in layer["shapes"] if shape["pin"]}
    extra = artwork_keys - registered.keys()
    checks.append(entry("artwork_pad_inventory", status="skipped" if extra else "ran",
                        reason="artwork_pins_not_registered" if extra else None))
    for island, rows in sorted(groups.items()):
        schematic_nets, ipc_nets = {p["schematic_net"] for p in rows}, {p["net"] for p in rows}
        items = [dict(reference=p["reference"], pin=p["pin"], pos=dict(zip(("x", "y"), p["position_mm"], strict=True))) for p in rows]
        if len(schematic_nets) > 1:
            findings.append(dict(type="gerber_schematic_short", severity="error", items=items,
                                 description="One physical artwork island joins distinct native schematic nets",
                                 layer=island[0], schematic_nets=sorted(schematic_nets), ipc_nets=sorted(ipc_nets),
                                 authority="Gerber geometry versus schematic; IPC remains PCB-derived"))
        if len(ipc_nets) > 1:
            findings.append(dict(type="gerber_ipc_short", severity="error", items=items,
                                 description="One physical artwork island joins distinct IPC net labels",
                                 layer=island[0], ipc_nets=sorted(ipc_nets)))
    # Compare member partitions, not truncated/renamed IPC net strings.
    partitions = defaultdict(list)
    for row in registered.values():
        partitions[row["net"]].append(row)
    for rows in partitions.values():
        sch = {row["schematic_net"] for row in rows}
        if len(sch) > 1:
            findings.append(dict(type="ipc_schematic_partition_conflict", severity="error",
                                 description="PCB-derived IPC member partition differs from native schematic intention",
                                 items=[dict(reference=p["reference"], pin=p["pin"]) for p in rows],
                                 schematic_nets=sorted(sch), ipc_net=rows[0]["net"]))
    intended = defaultdict(list)
    for row in registered.values():
        intended[row["schematic_net"]].append(row)
    for rows in intended.values():
        physical = {row["island"] for row in rows}
        if len(physical) > 1:
            if len({row["layer"] for row in rows}) > 1:
                checks.append(entry("interlayer_connection:" + rows[0]["schematic_net"], status="skipped",
                                    reason="plated_path_geometry_unverified", limit_id="L-FAB-CONNECTION-SUBSET"))
            else:
                findings.append(dict(type="gerber_schematic_open", severity="error",
                                     description="One native schematic net spans disconnected artwork islands on one layer",
                                     items=[dict(reference=p["reference"], pin=p["pin"]) for p in rows]))
    # Only surface access points are supported, so an interlayer open is not inferred.
    checks.append(entry("artwork_ipc_schematic_partitions"))
    for finding in findings:
        finding["confidence"] = "deterministic"
        finding["evidence_source"] = "topology" if finding["type"] == "ipc_schematic_partition_conflict" else "geometry"
    return normalize_findings(findings, "fab"), checks, list(registered.values())


def command(argv, root):
    output = run(argv, cwd=root, timeout=120)
    if output.returncode:
        raise PcbAiError("export_failed", "Native fabrication connection input export failed")


def check(root, document, expected_revision):
    started = time.monotonic()
    with snapshot(root, expected_revision) as copy, tempfile.TemporaryDirectory(prefix="pcbai-net-artwork-") as temporary:
        source = within(copy, document)
        schematic = within(copy, str(Path(document).with_suffix(".kicad_sch")))
        if source.suffix != ".kicad_pcb":
            raise PcbAiError("invalid_document", "Fabrication connection checks require a PCB")
        output = Path(temporary)
        copper = [layer["name"] for layer in summary(source.read_bytes())["layers"] if layer["name"].endswith(".Cu")]
        if not copper:
            raise PcbAiError("invalid_document", "No enabled copper layers")
        inner = sorted((name for name in copper if name not in {"F.Cu", "B.Cu"}), key=lambda name: int(name[2:-3]))
        copper = [*(name for name in ("F.Cu",) if name in copper), *inner, *(name for name in ("B.Cu",) if name in copper)]
        cli = find_kicad_cli()
        command([cli, "pcb", "export", "gerbers", source, "--layers", ",".join(copper),
                 "--no-protel-ext", "--check-zones", "--output", output], copy)
        command([cli, "pcb", "export", "ipcd356", source, "--output", output / "nets.d356"], copy)
        native_raw = export_netlist(copy, schematic.relative_to(copy).as_posix(), output / "schematic.xml")
        native = schematic_authority(native_raw)
        hashes = dict(board=digest(source.read_bytes()), schematic_netlist=digest(native_raw),
                      ipc_d356=digest((output / "nets.d356").read_bytes()))
        ipc = parse_ipc((output / "nets.d356").read_bytes())
        checks = [entry("ipc356_parser", inputs_sha256=hashes)]
        layers, files = {}, []
        claimed = set()
        for path in sorted(output.glob("*.gbr")):
            raw = path.read_bytes()
            layer_name = gerber_layer(path, copper)
            if layer_name in claimed:
                raise PcbAiError("invalid_report", "Duplicate fabrication copper layer")
            claimed.add(layer_name)
            files.append(dict(name=path.name, layer=layer_name, sha256=digest(raw)))
            try:
                layer = parse_gerber(raw)
                if layer["layer"] != layer_name:
                    raise PcbAiError("invalid_report", "Independent copper layer identity differs")
                layer["islands"] = islands(layer["shapes"])
                layers[layer_name] = layer
                checks.append(entry("gerber_geometry:" + layer_name, inputs_sha256={path.name: digest(raw)}))
            except PcbAiError as exc:
                checks.append(entry("gerber_geometry:" + layer_name, status="skipped", reason=exc.code,
                                    inputs_sha256={path.name: digest(raw)}, limit_id="L-FAB-CONNECTION-SUBSET"))
        for name in set(copper) - claimed:
            checks.append(entry("gerber_geometry:" + name, status="skipped", reason="missing_copper_file"))
        findings, registration, registered = reconcile(layers, ipc, native)
        checks.extend(registration)
        for row in checks:
            row.update(tool="fabrication_connections", seconds=time.monotonic()-started)
            if not row["inputs_sha256"]:
                row["inputs_sha256"] = hashes
        return dict(verified=verification(checks, findings), findings=findings, checks_run=checks, inputs_sha256=hashes,
                    copper_files=files, registered_pads=registered, original_revision=expected_revision,
                    production_verified=False, scope="positive standard-aperture linear surface artwork only",
                    ipc_intention_verified=False, interlayer_connectivity_verified=False,
                    limit_ids=["L-FAB-CONNECTION-SUBSET"])
