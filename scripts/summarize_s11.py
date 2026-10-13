"""Calibrate stored S11 outputs against KiCad evidence; no upstream imports."""
import json
import random
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pcbai.external import find_kicad_cli, find_kicad_python, run  # noqa: E402
from pcbai.kicad.exports import board_stats  # noqa: E402
from pcbai.kicad.files import revision  # noqa: E402

WORK = ROOT / ".pcbai-state/s11"


def main():
    result = json.loads((WORK / "result.json").read_text(encoding="utf-8"))
    findings = []
    for record in result["records"]:
        demo = record["demo"]
        sch = json.loads((WORK / f"{demo}-schematic-1.json").read_text(encoding="utf-8"))
        pcb = json.loads((WORK / f"{demo}-pcb-1.json").read_text(encoding="utf-8"))
        oracle = record["oracle_schematic"]
        refs = set(oracle["components"])
        # KiCad netlist omits graphical #PWR/#FLG symbols. Keep their omission explicit.
        external = {name: sorted((p["component"], p["pin_number"]) for p in net["pins"]
                                 if p["component"] in refs) for name, net in sch["nets"].items()}
        ignored = sorted({p["component"] for n in sch["nets"].values() for p in n["pins"]
                          if p["component"] not in refs})
        a = Counter(tuple(tuple(p) for p in pins) for pins in external.values())
        b = Counter(tuple(tuple(p) for p in pins) for pins in oracle["nets"].values())
        lost = list((b - a).elements())
        added = list((a - b).elements())
        matched_names = []
        by_members = {tuple(tuple(p) for p in pins): name for name, pins in oracle["nets"].items()}
        for name, pins in external.items():
            other = by_members.get(tuple(pins))
            if other is not None and name != other:
                matched_names.append(dict(external=name, kicad=other, members=pins))
        xml = ET.parse(WORK / f"{demo}-netlist.xml").getroot()
        sheets = xml.findall("./design/sheet")
        external_sheets = len(sch.get("sheets", ["root"]))
        external_refs = sorted({c["reference"] for c in sch["components"]})
        source = Path(find_kicad_cli()).parent.parent / "share/kicad/demos" / demo
        projects = sorted(source.glob("*.kicad_pro"))
        project = next((p for p in projects if p.stem == demo), projects[0])
        stats = board_stats(source, project.with_suffix(".kicad_pcb").name, revision(source))
        (WORK / f"{demo}-board-stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
        pad_count = sum(fp["pad_count"] for fp in pcb["footprints"])
        swig_process = run([find_kicad_python(), "-I", "-X", "utf8", ROOT / "scripts/s11_pcb_oracle.py",
                            project.with_suffix(".kicad_pcb")], cwd=WORK, timeout=60)
        if swig_process.returncode:
            raise RuntimeError(swig_process.stderr)
        swig = json.loads(swig_process.stdout)
        record["oracle_pcb"] = swig
        (WORK / f"{demo}-pcb-oracle-corrected.json").write_text(swig_process.stdout, encoding="utf-8")
        counts = {"footprints": [pcb["statistics"]["footprint_count"], swig["footprints"]],
                  "pads": [pad_count, swig["pads"]],
                  "tracks_including_arcs": [pcb["statistics"]["track_segments"],
                                            swig["track_segments"] + swig["track_arcs"]],
                  "straight_segments": [pcb["tracks"]["segment_count"], swig["track_segments"]],
                  "arcs": [pcb["tracks"]["arc_count"], swig["track_arcs"]],
                  "vias": [pcb["statistics"]["via_count"], swig["vias"]],
                  "zones": [pcb["statistics"]["zone_count"], swig["zones"]],
                  "nets": [pcb["statistics"]["net_count"], len(swig["nets"])],
                  "stats_footprints": [pcb["statistics"]["footprint_count"], stats["components"]["total"]["total"]],
                  "stats_pads": [pad_count, sum(stats["pads"].values())],
                  "stats_vias": [pcb["statistics"]["via_count"], sum(stats["vias"].values())],
                  "stats_front": [pcb["statistics"]["front_side"], stats["components"]["total"]["front"]],
                  "stats_back": [pcb["statistics"]["back_side"], stats["components"]["total"]["back"]],
                  "stats_smd": [pcb["statistics"]["smd_count"], stats["components"]["smd"]["total"]],
                  "stats_tht": [pcb["statistics"]["tht_count"], stats["components"]["tht"]["total"]],
                  "width_mm": [pcb["statistics"]["board_width_mm"], float(stats["board"]["width"].split()[0])],
                  "height_mm": [pcb["statistics"]["board_height_mm"], float(stats["board"]["height"].split()[0])]}
        record["calibration"] = dict(
            components=[sch["statistics"]["total_components"], len(refs)],
            component_references_equal=external_refs == sorted(refs),
            sheets=[external_sheets, len(sheets)], nets=[len(external), len(oracle["nets"])],
            net_members_equal=a == b, missing_member_groups=lost, extra_member_groups=added,
            net_member_sets_equal={frozenset(x) for x in a} == {frozenset(x) for x in b},
            net_name_differences=matched_names, ignored_graphical_power_symbols=ignored,
            pcb_counts=counts, board_stats=stats,
            note="Net names are retained; membership partitions compared independently of generated net names. "
                 "No power/flag pins exported by KiCad are removed. Multiplicity is preserved.")
        record["determinism"] = {}
        for kind in ("schematic", "pcb"):
            runs = [r for r in record["runs"] if r["kind"] == kind]
            record["determinism"][kind] = dict(
                finding_id_sets_equal=set(runs[0]["finding_ids"]) == set(runs[1]["finding_ids"]),
                finding_id_lists_equal=runs[0]["finding_ids"] == runs[1]["finding_ids"],
                raw_sha256_equal=runs[0]["output_sha256"] == runs[1]["output_sha256"])
            data = sch if kind == "schematic" else pcb
            for f in data["findings"]:
                findings.append(dict(demo=demo, kind=kind, finding=f))
        print(demo, "members", a == b, "missing", len(lost), "extra", len(added), "counts", counts, flush=True)
    result["sample_seed"] = 11013
    result["sample_population"] = len(findings)
    result["manual_sample"] = random.Random(result["sample_seed"]).sample(
        sorted(findings, key=lambda f: (f["demo"], f["kind"], f["finding"]["finding_id"])), 20)
    (WORK / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (WORK / "sample.json").write_text(json.dumps(result["manual_sample"], ensure_ascii=False, indent=2), encoding="utf-8")
    run(["git", "-C", WORK / "kicad-happy", "status", "--short"], timeout=20)


if __name__ == "__main__":
    main()
