"""Trusted bridge executed only by a configured external pcb-dfm Python environment."""
import json
import sys
import hashlib
from pathlib import Path
from importlib.metadata import version


def main():
    from pcb_dfm.engine.run import run_dfm_on_gerber_zip, build_geometry_for
    from pcb_dfm.geometry.gerber_backend import excellon_hits_mm, excellon_slots_mm, gerber_edges_mm
    request = json.loads(Path(sys.argv[1]).read_bytes()[:16385])
    package = Path(request["package"])
    report = run_dfm_on_gerber_zip(package, ruleset_id=request["ruleset"])
    Path(request["report"]).write_text(report.to_json(), encoding="utf-8")
    geometry = build_geometry_for(package)
    hits, slots, edges = [], [], []
    copper, mask = [], []
    for layer in geometry.layers:
        if layer.layer_type == "copper":
            copper.extend(file.original_name for file in layer.files)
        if layer.layer_type == "mask":
            mask.extend(file.original_name for file in layer.files)
        for file in layer.files:
            if layer.layer_type == "drill":
                hits.extend(excellon_hits_mm(file.path))
                slots.extend(excellon_slots_mm(file.path))
            elif layer.layer_type == "outline":
                edges.extend(gerber_edges_mm(file.path))
    # Native board statistics report centreline bounds, not the drawn stroke envelope.
    # Curved outline bounds need a separately calibrated arc model; never guess.
    bounds = None
    if edges and all(edge[2] == "line" for edge in edges):
        points = [point for edge in edges for point in edge[:2]]
        bounds = dict(width_mm=max(point[0] for point in points)-min(point[0] for point in points),
                      height_mm=max(point[1] for point in points)-min(point[1] for point in points))
    calibration = dict(schema_version=1, pcb_dfm_package_version=version("pcb-dfm"),
                       gerbonara_version=version("gerbonara"), copper_files=copper, mask_files=mask,
                       drill_hits=len(hits), drill_slots=len(slots), outline_bounds=bounds,
                       outline_bounds_kind="linear_centreline" if bounds else "unavailable_or_curved",
                       geometry_source="gerber", package_sha256=hashlib.sha256(package.read_bytes()).hexdigest(),
                       copper_file_order_verified=False)
    Path(request["calibration"]).write_text(json.dumps(calibration, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
