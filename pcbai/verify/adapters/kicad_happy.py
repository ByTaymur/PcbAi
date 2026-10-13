"""Project bounded kicad-happy JSON reports onto the calibration model."""
import json

from pcbai.core.contract import PcbAiError


def from_reports(schematic, pcb=None):
    if isinstance(schematic, (bytes, str)):
        if len(schematic) > 64 * 1024 * 1024:
            raise PcbAiError("invalid_model", "External report exceeds limits")
        try:
            schematic = json.loads(schematic)
        except (ValueError, UnicodeError) as exc:
            raise PcbAiError("invalid_model", "Invalid external JSON") from exc
    if not isinstance(schematic, dict):
        raise PcbAiError("invalid_model", "External report must be an object")
    try:
        components = sorted({c["reference"] for c in schematic["components"] if not c["reference"].startswith("#")})
        nets = {name: [[p["component"], p["pin_number"]] for p in net["pins"] if not p["component"].startswith("#")]
                for name, net in schematic["nets"].items()}
        sheets = schematic.get("sheets")
        # Pinned upstream omits 'sheets' for the single-file analyzer, but records
        # that one input explicitly. Do not infer a root for reports without provenance.
        sources = schematic.get("inputs", {}).get("source_files", [])
        if sheets is None and isinstance(sources, list) and len(sources) == 1 and isinstance(sources[0], str) and sources[0]:
            sheets = sources
        if sheets is not None and (not isinstance(sheets, list) or not sheets
                                   or any(not isinstance(s, str) or not s for s in sheets)):
            raise PcbAiError("invalid_model", "External sheets must be a nonempty text list")
        model = dict(components=components, sheet_instances=len(sheets) if sheets is not None else None, nets=nets)
        if pcb is not None:
            model.update(footprints=pcb["statistics"]["footprint_count"],
                         pads=sum(fp["pad_count"] for fp in pcb["footprints"]),
                         vias=pcb["statistics"]["via_count"], segments=pcb["statistics"]["track_segments"])
        return model
    except (KeyError, TypeError, AttributeError) as exc:
        raise PcbAiError("invalid_model", "External report fields are missing or invalid") from exc
