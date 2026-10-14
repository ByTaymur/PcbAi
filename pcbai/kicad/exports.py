"""CLI artifacts are generated from a revision-bound copy, never the user's board."""
import json
import csv
import math
import re
import tempfile
import zipfile
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli, run
from pcbai.kicad.cli import snapshot
from pcbai.kicad.files import digest, within
from pcbai.sexpr import Document


def command(argv, cwd):
    process = run(argv, cwd=cwd, timeout=120)
    if process.returncode:
        raise PcbAiError("export_failed", f"KiCad export failed (exit {process.returncode}): "
                         + (process.stderr or process.stdout)[-2000:])


def board_stats(root, document, expected_revision):
    with snapshot(root, expected_revision) as copy:
        destination = copy / "pcbai-stats.json"
        command([find_kicad_cli(), "pcb", "export", "stats", within(copy, document),
                 "--format", "json", "--units", "mm", "--output", destination], copy)
        try:
            report = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PcbAiError("invalid_report", "KiCad did not produce a valid statistics report") from exc
        stats_measurements(report)
        return report


def stats_measurements(report):
    try:
        board = report["board"]
        if not isinstance(board["has_outline"], bool):
            raise ValueError("invalid outline flag")
        values = []
        for dimension in ("width", "height"):
            text = board[dimension]
            if not isinstance(text, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)? mm", text):
                raise ValueError("invalid dimension")
            value = float(text[:-3])
            if not math.isfinite(value):
                raise ValueError("nonfinite dimension")
            values.append(dict(quantity="board_" + dimension, value=value, unit="mm"))
        count = report["components"]["total"]["total"]
        if type(count) is not int or count < 0:
            raise ValueError("invalid component count")
        values.append(dict(quantity="footprints", value=count, unit="count"))
        return values
    except (KeyError, TypeError, ValueError) as exc:
        raise PcbAiError("invalid_report", "KiCad statistics report has invalid geometry or component totals") from exc


def render_board(root, document, destination, expected_revision, *, side="top", width=800, height=600):
    with snapshot(root, expected_revision) as copy:
        command([find_kicad_cli(), "pcb", "render", within(copy, document), "--output", destination,
                 "--side", side, "--width", str(width), "--height", str(height), "--quality", "basic"], copy)
        try:
            data = Path(destination).read_bytes()
        except OSError as exc:
            raise PcbAiError("export_failed", "KiCad did not create a render") from exc
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise PcbAiError("export_failed", "KiCad did not produce a PNG image")
        dimensions = dict(width=int.from_bytes(data[16:20], "big"), height=int.from_bytes(data[20:24], "big"))
        if not all(0 < n <= 2048 for n in dimensions.values()):
            raise PcbAiError("export_failed", "Rendered image has invalid dimensions")
        return dimensions


def gerber_layer(path, copper_stack):
    with path.open("r", encoding="utf-8") as stream:
        header = stream.read(16384)
    functions = re.findall(r"%TF\.FileFunction,([^*]+)\*%", header)
    if len(functions) != 1:
        raise PcbAiError("export_failed", "Gerber has no unique X2 FileFunction")
    if re.findall(r"%MO(MM|IN)\*%", header) != ["MM"]:
        raise PcbAiError("export_failed", "Gerber units do not match the millimetre package contract")
    words = functions[0].split(",")
    if words[0] == "Copper" and len(words) >= 3:
        try:
            index = int(words[1][1:]) - 1 if words[1].startswith("L") else -1
            if not 0 <= index < len(copper_stack):
                raise ValueError()
            layer = copper_stack[index]
            face = "Top" if layer == "F.Cu" else "Bot" if layer == "B.Cu" else "Inr"
            if words[2] != face:
                raise ValueError()
            return layer
        except ValueError as exc:
            raise PcbAiError("export_failed", "Gerber copper layer disagrees with source stack") from exc
    if words[0] == "Profile":
        return "Edge.Cuts"
    kind = {"Soldermask": "Mask", "Legend": "Silkscreen", "Paste": "Paste"}.get(words[0])
    if kind and len(words) >= 2 and words[1] in {"Top", "Bot"}:
        return ("F." if words[1] == "Top" else "B.") + kind
    raise PcbAiError("export_failed", "Unsupported Gerber layer function")


def export_fab(root, document, destination, expected_revision, *, assembly=False, profile=None):
    with snapshot(root, expected_revision) as copy, tempfile.TemporaryDirectory(prefix="pcbai-fab-") as temporary:
        profile_check = None
        if profile is not None:
            from pcbai.fab.profile import check_copy
            profile_check = check_copy(copy, document, expected_revision, profile)
            if not profile_check["clean"]:
                raise PcbAiError("fab_profile_blocked", "Native strict fabrication profile check did not pass",
                                 details={"profile_check": profile_check})
        output = Path(temporary)
        cli = find_kicad_cli()
        source = within(copy, document)
        layer_table = Document(source.read_bytes()).root.child("layers")
        if layer_table is None:
            raise PcbAiError("invalid_document", "Fabrication export requires an enabled layer stack")
        copper = [n.value() for n in layer_table.children[1:]
                  if n.atom is None and (n.value() or "").endswith(".Cu")]
        if not copper:
            raise PcbAiError("invalid_document", "Fabrication export requires an enabled copper layer stack")
        inner = sorted((n for n in copper if n not in {"F.Cu", "B.Cu"}),
                       key=lambda name: int(re.fullmatch(r"In([0-9]+)\.Cu", name).group(1)))
        copper = [*(name for name in ("F.Cu",) if name in copper), *inner,
                  *(name for name in ("B.Cu",) if name in copper)]
        # Include every enabled copper layer, masks, silk and the outline. Refill only the copy.
        command([cli, "pcb", "export", "gerbers", source, "--output", output,
                 "--layers", "*.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts"
                 + (",F.Paste,B.Paste" if assembly else ""), "--check-zones",
                 "--no-protel-ext"], copy)
        command([cli, "pcb", "export", "drill", source, "--output", output,
                 "--format", "excellon", "--excellon-units", "mm", "--drill-origin", "absolute"], copy)
        command([cli, "pcb", "export", "ipcd356", source, "--output", output / "nets.d356"], copy)
        for side in ("front", "back"):
            command([cli, "pcb", "export", "pos", source, "--output", output / f"positions-{side}.csv",
                     "--format", "csv", "--units", "mm", "--side", side], copy)
        command([cli, "pcb", "export", "stats", source, "--output", output / "board-stats.json",
                 "--format", "json", "--units", "mm"], copy)
        files = sorted(output.iterdir())
        if any(p.is_symlink() or getattr(p.lstat(), "st_file_attributes", 0) & 0x400
               or not p.is_file() or p.stat().st_size == 0 for p in files):
            raise PcbAiError("export_failed", "Empty or unsafe export file")
        if not any(p.suffix == ".gbr" for p in files) or not any(p.suffix == ".drl" for p in files):
            raise PcbAiError("export_failed", "KiCad export is missing Gerber or drill files")
        layers = {path.name: gerber_layer(path, copper) for path in files if path.suffix == ".gbr"}
        if len(set(layers.values())) != len(layers):
            raise PcbAiError("export_failed", "Several Gerbers claim the same layer")
        enabled = {node.value() for node in layer_table.children[1:] if node.atom is None}
        enabled = {layer.replace(".SilkS", ".Silkscreen") for layer in enabled}
        fabrication_layers = ["F.Mask", "B.Mask", "F.Silkscreen", "B.Silkscreen", "Edge.Cuts"]
        expected_layers = [*copper, *(layer for layer in fabrication_layers if layer in enabled)]
        if assembly:
            expected_layers.extend(["F.Paste", "B.Paste"])
        for layer in expected_layers:
            if layer not in layers.values():
                raise PcbAiError("export_failed", "Missing requested Gerber layer: " + layer)
        required = {"nets.d356", "positions-front.csv", "positions-back.csv", "board-stats.json"}
        if not required <= {p.name for p in files}:
            raise PcbAiError("export_failed", "KiCad export is missing netlist, positions or statistics")
        try:
            stats_measurements(json.loads((output / "board-stats.json").read_text(encoding="utf-8")))
            ipc = (output / "nets.d356").read_text(encoding="utf-8")
            if not any(line.startswith("999") for line in ipc.splitlines()):
                raise ValueError("Incomplete IPC-D-356")
            seen_refs = set()
            for side in ("front", "back"):
                with (output / f"positions-{side}.csv").open(encoding="utf-8-sig", newline="") as stream:
                    reader = csv.DictReader(stream)
                    if reader.fieldnames != ["Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"]:
                        raise ValueError("Unsupported native position columns")
                    for row in reader:
                        if (not row["Ref"] or row["Ref"] in seen_refs or None in row
                                or row["Side"] != ("top" if side == "front" else "bottom")
                                or any(not math.isfinite(float(row[k])) for k in ("PosX", "PosY", "Rot"))):
                            raise ValueError("Invalid position row")
                        seen_refs.add(row["Ref"])
        except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
            raise PcbAiError("export_failed", "Native assembly/netlist/statistics output is invalid") from exc
        entries = []
        for path in files:
            role = ("ipc_d356" if path.name == "nets.d356" else "board_statistics" if path.name == "board-stats.json"
                    else "position_front_raw" if path.name == "positions-front.csv"
                    else "position_back_raw" if path.name == "positions-back.csv"
                    else "gerber_job" if path.suffix == ".gbrjob" else "drill" if path.suffix == ".drl"
                    else "gerber" if path.suffix == ".gbr" else "native_auxiliary")
            entry = dict(name=path.name, role=role, sha256=digest(path.read_bytes()), bytes=path.stat().st_size)
            if path.suffix == ".gbr":
                entry["layer"] = layers[path.name]
            entries.append(entry)
        manifest = dict(schema_version=1, document=document, revision=expected_revision, production_verified=False,
                        assembly_requested=assembly, units="mm", coordinate_origin="absolute",
                        ipc_units="native_header", ipc_coordinates="native_not_calibrated",
                        position_policy="native_eligible_footprints_unmirrored",
                        position_filters=dict(native_exclusion_flags_respected=True, smd_only=False, exclude_dnp=False),
                        omitted_disabled_layers=[layer for layer in fabrication_layers if layer not in enabled],
                        files=entries)
        if profile_check is not None:
            manifest["profile_check"] = profile_check
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, path.name)
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        return manifest
