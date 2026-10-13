"""Revision-bound KiCad GLB for the 3D view; component references come from GLB node names (S9)."""

import json
import re
import shutil
import struct
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli
from pcbai.kicad.cli import snapshot
from pcbai.kicad.exports import command
from pcbai.kicad.files import digest, within

MAX_BYTES = 96 * 1024 * 1024


def glb_json(data):
    """Validate a binary glTF 2.0 container and return its JSON chunk. External/remote resources are refused."""
    if len(data) < 28 or len(data) > MAX_BYTES:
        raise PcbAiError("unsafe_glb", "GLB is empty or exceeds the size limit")
    magic, version, length = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or length != len(data):
        raise PcbAiError("unsafe_glb", "Not a binary glTF 2.0 file")
    size, kind = struct.unpack_from("<I4s", data, 12)
    if kind != b"JSON" or 20 + size > len(data):
        raise PcbAiError("unsafe_glb", "GLB JSON chunk is missing")
    try:
        document = json.loads(data[20:20 + size])
    except (ValueError, UnicodeError) as exc:
        raise PcbAiError("unsafe_glb", "GLB JSON chunk is invalid") from exc
    for group in ("buffers", "images"):
        for item in document.get(group, []):
            if "uri" in item:  # KiCad embeds everything in the BIN chunk; any URI would be fetched by a loader
                raise PcbAiError("unsafe_glb", "GLB references an external or data URI")
    if document.get("extensionsRequired"):
        raise PcbAiError("unsafe_glb", "GLB requires extensions the viewer does not load")
    return document


def component_nodes(document, references):
    """Map footprint references to GLB node indices by exact node name; unmatched names are reported."""
    nodes = document.get("nodes", [])
    wanted = set(references)
    matched, seen = {}, set()
    for index, node in enumerate(nodes):
        name = node.get("name")
        if name in wanted:
            matched.setdefault(name, []).append(index)
            seen.add(name)
    return matched, sorted(wanted - seen)


def model_substitutions(data, library):
    """Display-only fixes for a disposable copy: legacy ${KICADn_3DMODEL_DIR} names and .wrl → installed .step."""
    count = 0

    def fix(match):
        nonlocal count
        path = match.group(2)
        new = re.sub(r"\$\{KICAD[5-9]_3DMODEL_DIR\}", "${KICAD10_3DMODEL_DIR}", path)
        relative = new.replace("${KICAD10_3DMODEL_DIR}/", "", 1)
        if new.startswith("${KICAD10_3DMODEL_DIR}/") and relative.lower().endswith(".wrl"):
            step = relative[:-4] + ".step"
            if (library / step).is_file() and not (library / relative).is_file():
                new = new[:-4] + ".step"
        if new != path:
            count += 1
        return match.group(1) + new + match.group(3)

    text = data.decode("utf-8")
    changed = re.sub(r'(\(model ")([^"]+)(")', fix, text)
    return changed.encode("utf-8"), count


def render_3d(root, document, revision, destination, references):
    """Caller serializes this cache and validates the source revision before/after."""
    cache = Path(destination) / ("glb-" + digest(document.encode())[:24])
    manifest = cache / "manifest.json"
    if manifest.is_file():
        report = json.loads(manifest.read_text(encoding="utf-8"))
        path = Path(report.get("path", ""))
        if (report.get("document") == document and report.get("revision") == revision and path.is_file()
                and path.resolve().is_relative_to(cache.resolve()) and digest(path.read_bytes()) == report["sha256"]):
            return report
    cache.mkdir(parents=True, exist_ok=True)
    try:
        with snapshot(root, revision) as copy:
            output = copy / "pcbai-board.glb"
            library = Path(find_kicad_cli()).parent.parent / "share" / "kicad" / "3dmodels"
            source = within(copy, document)
            fixed, substitutions = model_substitutions(source.read_bytes(), library)
            source.write_bytes(fixed)
            command([find_kicad_cli(), "pcb", "export", "glb", within(copy, document), "--output", output, "--force",
                     "--include-silkscreen", "--include-soldermask", "--include-pads"], copy)
            data = output.read_bytes()
            gltf = glb_json(data)
            target = cache / "board.glb"
            target.write_bytes(data)
        matched, missing = component_nodes(gltf, references)
        report = dict(document=document, revision=revision, path=str(target), sha256=digest(data), bytes=len(data),
                      units="m", components=sorted(matched), nodes=matched, without_model=missing,
                      selectable=bool(matched), display_model_substitutions=substitutions)
        manifest.write_text(json.dumps(report, allow_nan=False), encoding="utf-8")
        return report
    except Exception:
        if cache.resolve().is_relative_to(Path(destination).resolve()):
            shutil.rmtree(cache)
        raise
