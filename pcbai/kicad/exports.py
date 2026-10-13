"""CLI artifacts are generated from a revision-bound copy, never the user's board."""
import json
import math
import re
import tempfile
import zipfile
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli, run
from pcbai.kicad.cli import snapshot
from pcbai.kicad.files import digest, within


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


def export_fab(root, document, destination, expected_revision):
    with snapshot(root, expected_revision) as copy, tempfile.TemporaryDirectory(prefix="pcbai-fab-") as temporary:
        output = Path(temporary)
        cli = find_kicad_cli()
        source = within(copy, document)
        # Include every enabled copper layer, masks, silk and the outline. Refill only the copy.
        command([cli, "pcb", "export", "gerbers", source, "--output", output,
                 "--layers", "*.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts", "--check-zones",
                 "--no-protel-ext"], copy)
        command([cli, "pcb", "export", "drill", source, "--output", output,
                 "--format", "excellon", "--excellon-units", "mm"], copy)
        files = sorted(p for p in output.iterdir() if p.is_file())
        if not any(p.suffix == ".gbr" for p in files) or not any(p.suffix == ".drl" for p in files):
            raise PcbAiError("export_failed", "KiCad export is missing Gerber or drill files")
        manifest = dict(document=document, revision=expected_revision, production_verified=False,
                        files=[dict(name=p.name, sha256=digest(p.read_bytes()), bytes=p.stat().st_size) for p in files])
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, path.name)
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        return manifest
