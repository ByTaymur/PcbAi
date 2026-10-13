"""Read/flatten KiCad symbol inheritance and inspect physical pins/pads."""
import os
import re
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli
from pcbai.kicad.files import digest, within
from pcbai.pcb.edit import quoted
from pcbai.sch.model import properties
from pcbai.sexpr import Document
from pcbai.views import number

UNIT = re.compile(r"_(\d+)_(\d+)$")


def roots():
    installation = (Path(find_kicad_cli()).resolve().parents[1] / "share/kicad"
                    if not (os.environ.get("PCBAI_SYMBOLS") and os.environ.get("PCBAI_FOOTPRINTS")) else Path("."))
    return (Path(os.environ.get("PCBAI_SYMBOLS", installation / "symbols")).resolve(),
            Path(os.environ.get("PCBAI_FOOTPRINTS", installation / "footprints")).resolve())


def identifier(value):
    if not isinstance(value, str) or value.count(":") != 1:
        raise PcbAiError("invalid_arguments", "Use Library:Part identifier")
    library, name = value.split(":")
    if (not re.fullmatch(r"[A-Za-z0-9_.+-]+", library) or library in {".", ".."} or not name
            or any(c in name for c in '/\\') or
            any(ord(c) < 32 or 127 <= ord(c) <= 159 or 0xD800 <= ord(c) <= 0xDFFF for c in name) or name in {".", ".."}):
        raise PcbAiError("invalid_arguments", "Invalid library identifier")
    return library, name


def read_library(path):
    if path.stat().st_size > 64 * 1024 * 1024:
        raise PcbAiError("invalid_library", "Library is too large")
    data = path.read_bytes()
    doc = Document(data)
    if doc.root.name != "kicad_symbol_lib":
        raise PcbAiError("invalid_library", "Expected a KiCad symbol library")
    nodes = {}
    for node in doc.root.all("symbol"):
        if node.value() in nodes:
            raise PcbAiError("invalid_library", "Duplicate symbol definitions")
        nodes[node.value()] = node
    return data, nodes


METADATA_TOKENS = re.compile(rb'\(|\)|"(?:[^"\\]|\\.)*"|;[^\r\n]*|[^()";]+')


def read_metadata(path):
    """Scan balanced library syntax; build CSTs only for metadata, not graphics/pins.

    This is an index scan, not a symbol validation. Authoring/part_info still use
    the full strict parser. Large pin/graphics subtrees need no Python Node objects.
    """
    if path.stat().st_size > 64 * 1024 * 1024:
        raise PcbAiError("invalid_library", "Library is too large")
    data = path.read_bytes()
    frames, nodes, roots_count, last = [], {}, 0, 0
    for token in METADATA_TOKENS.finditer(data):
        if data[last:token.start()].strip():
            raise PcbAiError("invalid_library", "Unterminated quoted library text")
        last = token.end()
        raw = token.group()
        if raw.startswith(b';') or not raw.strip():
            continue
        if raw == b'(':
            if len(frames) >= 1024:
                raise PcbAiError("invalid_library", "Library syntax is too deeply nested")
            frames.append(dict(start=token.start(), kind=None, name=None, fields=[]))
        elif raw == b')':
            if not frames:
                raise PcbAiError("invalid_library", "Unbalanced library syntax")
            frame = frames.pop()
            if not frames:
                if frame["kind"] != "kicad_symbol_lib":
                    raise PcbAiError("invalid_library", "Expected a KiCad symbol library")
                roots_count += 1
            elif len(frames) == 1 and frame["kind"] == "symbol":
                if frame["name"] is None:
                    raise PcbAiError("invalid_library", "Symbol name must be quoted")
                node = Document(b'(symbol ' + frame["name"] + b' ' + b' '.join(frame["fields"]) + b')').root
                if node.value() in nodes:
                    raise PcbAiError("invalid_library", "Duplicate symbol definitions")
                nodes[node.value()] = node
            elif len(frames) == 2 and frames[-1]["kind"] == "symbol" and frame["kind"] in {"property", "extends"}:
                frames[-1]["fields"].append(data[frame["start"]:token.end()])
        elif not frames:
            raise PcbAiError("invalid_library", "Text outside library root")
        elif frames[-1]["kind"] is None:
            frames[-1]["kind"] = raw.strip().split()[0].decode("utf-8")
        elif len(frames) == 2 and frames[-1]["kind"] == "symbol" and frames[-1]["name"] is None:
            if not raw.startswith(b'"'):
                raise PcbAiError("invalid_library", "Symbol name must be quoted")
            frames[-1]["name"] = raw
    if frames or roots_count != 1 or data[last:].strip():
        raise PcbAiError("invalid_library", "Incomplete or multiple library roots")
    return data, nodes


def flatten(data, definitions, name, lib_id, *, cached=False):
    """Resolve a strict, bounded inheritance chain, including project-cache names."""
    def inherited(key, seen=()):
        if key not in definitions or key in seen or len(seen) >= 16:
            raise PcbAiError("invalid_library", "Symbol inheritance is missing, cyclic or too deep")
        node = definitions[key]
        parent = node.child("extends")
        parent_key = parent.value() if parent else None
        if cached and parent_key and ":" not in parent_key and ":" in key:
            parent_key = key.split(":", 1)[0] + ":" + parent_key
        result = inherited(parent_key, (*seen, key)) if parent else {}
        own_keys = set()
        for child in node.children[2:]:
            if child.atom is not None or child.name == "extends":
                continue
            if child.name == "property":
                kind = ("property", child.value())
            elif child.name == "symbol":
                match = UNIT.search(child.value() or "")
                if not match:
                    raise PcbAiError("invalid_library", "Unrecognized symbol unit/body name")
                kind = ("symbol", match.groups())
            else:
                kind = (child.name, None)
            if kind in own_keys:
                raise PcbAiError("invalid_library", "Duplicate symbol fields or unit/body definitions")
            own_keys.add(kind)
            result[kind] = (child, data)
        return result

    if name not in definitions:
        raise PcbAiError("unknown_part", "Symbol is absent from the configured KiCad library")
    chunks = []
    for (kind, key), (node, source) in inherited(name).items():
        raw = source[node.start:node.end]
        if kind == "symbol":
            atom = node.children[1]
            replacement = quoted(name + "_" + "_".join(key)).encode("utf-8")
            raw = raw[:atom.start - node.start] + replacement + raw[atom.end - node.start:]
        chunks.append(raw)
    flattened = b'(symbol ' + quoted(lib_id).encode() + b'\n' + b'\n'.join(chunks) + b')'
    return flattened


def inspect_symbol(flattened, lib_id):
    root = Document(flattened).root
    pins, units = [], set()
    for sub in root.all("symbol"):
        match = UNIT.search(sub.value())
        unit, style = map(int, match.groups())
        if style not in {0, 1}:
            continue
        if unit:
            units.add(unit)
        for pin in sub.all("pin"):
            at, pin_name, pin_number = pin.child("at"), pin.child("name"), pin.child("number")
            if at is None or pin_number is None:
                raise PcbAiError("invalid_library", "Pin definition is incomplete")
            pins.append(dict(number=pin_number.value(), name=pin_name.value() if pin_name else "", unit=unit,
                             electrical_type=pin.value(), at=[number(at.value()), number(at.value(2))],
                             rotation=number(at.value(3, "0"))))
    return dict(lib_id=lib_id, properties=properties(root), pins=pins, units=sorted(units) or [1], data=flattened)


def symbol(lib_id):
    library, name = identifier(lib_id)
    symbol_root, _ = roots()
    path = within(symbol_root, library + ".kicad_sym")
    data, definitions = read_library(path)
    return dict(inspect_symbol(flatten(data, definitions, name, lib_id), lib_id),
                path=str(path), library_sha256=digest(data), source="kicad", trusted=False,
                license="unknown" if os.environ.get("PCBAI_SYMBOLS") else "CC-BY-SA-4.0 WITH KiCad-libraries-exception")


def footprint(lib_id):
    library, name = identifier(lib_id)
    _, footprint_root = roots()
    path = within(footprint_root, library + ".pretty/" + name + ".kicad_mod")
    if path.stat().st_size > 16 * 1024 * 1024:
        raise PcbAiError("invalid_library", "Footprint is too large")
    data = path.read_bytes()
    node = Document(data).root
    if node.name not in {"footprint", "module"}:
        raise PcbAiError("invalid_library", "Expected a KiCad footprint")
    pads = []
    for pad in node.all("pad"):
        at = pad.child("at")
        pads.append(dict(number=pad.value(), type=pad.value(2), shape=pad.value(3),
                         at=[number(at.value()), number(at.value(2))] if at else None))
    return dict(lib_id=lib_id, pads=pads, data=data, path=str(path), sha256=digest(data), source="kicad",
                trusted=False, license="unknown" if os.environ.get("PCBAI_FOOTPRINTS") else "CC-BY-SA-4.0 WITH KiCad-libraries-exception")


def verify_part(symbol_id, footprint_id, datasheet_pins=None):
    sym, fp = symbol(symbol_id), footprint(footprint_id)
    pins = {p["number"] for p in sym["pins"]}
    pads = {p["number"] for p in fp["pads"] if p["number"] and p["type"] in {"smd", "thru_hole", "connect"}}
    missing, extra = sorted(pins - pads), sorted(pads - pins)
    warnings = []
    mechanical = [p for p in fp["pads"] if p["type"] == "np_thru_hole" or not p["number"]]
    if any(p["number"] for p in mechanical):
        warnings.append("Numbered mechanical/NPTH pads do not count as electrical pin counterparts")
    datasheet_match = None
    if datasheet_pins is not None:
        actual = {p["number"]: p["name"] for p in sym["pins"]}
        datasheet_match = actual == datasheet_pins
        if not datasheet_match:
            warnings.append("Caller-supplied datasheet pin table does not match; human review required")
    else:
        warnings.append("No independent datasheet pin table provided")
    warnings += ["Stock, lifecycle and 3D package dimensions have not been verified"]
    return dict(symbol=symbol_id, footprint=footprint_id, pin_numbers=sorted(pins), pad_numbers=sorted(pads),
                mechanical_pads=mechanical,
                pin_pad_match=bool(pins) and pins == pads, missing_pads=missing, extra_pads=extra,
                datasheet_match=datasheet_match, datasheet_source="caller_supplied" if datasheet_pins is not None else None,
                stock_verified=False, lifecycle_verified=False, model_3d_verified=False,
                warnings=warnings, symbol_library_sha256=sym["library_sha256"], footprint_sha256=fp["sha256"])
