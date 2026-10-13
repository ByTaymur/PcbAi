"""RD-G2: generate owned minimal projects and measure existing behavior, no detector code."""
import json
import os
import shutil
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pcbai.external import find_kicad_cli, find_kicad_python, run  # noqa: E402
from pcbai.sch.edit import endpoint, plan_add_symbol, plan_labels  # noqa: E402
from pcbai.sexpr import Document  # noqa: E402
from pcbai.tools.engine import Engine  # noqa: E402
from scripts.spike_kicad_happy import hashes, reject_links  # noqa: E402


def schematic(name, *, empty=False):
    uid = str(uuid.uuid4())
    data = (f'(kicad_sch (version 20260101) (generator "pcbai") (generator_version "10.0") (uuid "{uid}") '
            '(paper "A4") (lib_symbols) (embedded_fonts no))').encode()
    context = dict(project=name, sheet_path="/" + uid, root_uuid=uid, references=[])
    ids = []
    if empty:
        return data, uid, ids
    for reference, x, net in [("J1", 25.4, "LEFT"), ("J2", 50.8, "RIGHT")]:
        candidate = plan_add_symbol(data, dict(lib_id="Connector_Generic:Conn_01x01", reference=reference,
                                              value="Conn_01x01", x_mm=x, y_mm=50.8), context)
        data = candidate["data"]
        ids.append(candidate["symbol_uuid"])
        pin = endpoint(data, dict(reference=reference, pin="1"), context)
        data = plan_labels(data, dict(name=net, x_mm=pin["at"][0], y_mm=pin["at"][1]), context)["data"]
    return data, uid, ids


def board(root_uid, ids, merged, descriptions):
    # Two rectangular pads joined by one trace. Deliberately falsify J2's assigned net for #1.
    fps = []
    for i, (reference, x) in enumerate([("J1", 5), ("J2", 10)]):
        net = "LEFT" if merged or i == 0 else "RIGHT"
        fps.append(f'''(footprint "" (layer "F.Cu") (at {x} 5) (uuid "{uuid.uuid4()}")
          (property "Reference" "{reference}" (at 0 -2 0) (layer "F.SilkS") (hide yes)
            (effects (font (size 1 1) (thickness 0.15))))
          (property "Value" "Conn_01x01" (at 0 2 0) (layer "F.Fab") (hide yes)
            (effects (font (size 1 1) (thickness 0.15))))
          (property "Description" {json.dumps(descriptions[i])} (at 0 0 0) (layer "F.Fab") (hide yes)
            (effects (font (size 1 1) (thickness 0.15))))
          (path "/{root_uid}/{ids[i]}") (attr smd)
          (fp_rect (start -1 -1) (end 1 1) (stroke (width 0.05) (type default))
            (fill none) (layer "F.CrtYd") (uuid "{uuid.uuid4()}"))
          (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Paste" "F.Mask")
            (net {1 if net == 'LEFT' else 2} "/{net}") (uuid "{uuid.uuid4()}")))''')
    track = (f'(segment (start 5 5) (end 10 5) (width 0.25) (layer "F.Cu") (net 1) '
             f'(uuid "{uuid.uuid4()}"))') if merged else ""
    return ('''(kicad_pcb (version 20241229) (generator "pcbnew") (general (thickness 1.6))
      (paper "A4") (layers (0 "F.Cu" signal) (2 "B.Cu" signal)
        (1 "F.Mask" user) (3 "B.Mask" user) (5 "F.SilkS" user "F.Silkscreen")
        (13 "F.Paste" user) (31 "F.CrtYd" user "F.Courtyard") (35 "F.Fab" user)
        (25 "Edge.Cuts" user)) (setup (pad_to_mask_clearance 0))
      (net 0 "") (net 1 "/LEFT") ''' + ('' if merged else '(net 2 "/RIGHT")') +
            "\n".join(fps) + track +
            f'''(gr_rect (start 0 0) (end 15 10) (stroke (width 0.05) (type default))
              (fill none) (layer "Edge.Cuts") (uuid "{uuid.uuid4()}")))''').encode()


def main():
    work = ROOT / ".pcbai-state/s11/faults"
    work.resolve().relative_to(ROOT)
    work.mkdir(parents=True, exist_ok=True)
    fixtures = ROOT / "tests/fixtures/faults"
    fixtures.resolve().relative_to(ROOT)
    results = {}
    cli = find_kicad_cli()
    python = find_kicad_python()
    for number, slug in [(1, "01-drc-zero-short"), (9, "09-wrong-net-members"), (12, "12-missing-required-tool")]:
        folder = fixtures / slug
        folder.mkdir(parents=True, exist_ok=True)
        reject_links(folder)
        # Run without --generate to remeasure the committed fixture verbatim.
        if "--generate" in sys.argv:
            data, root_uid, ids = schematic("fault", empty=number == 12)
            (folder / "fault.kicad_pro").write_text("{}\n", encoding="utf-8")
            (folder / "fault.kicad_sch").write_bytes(data)
            # Native KiCad save on a private copy establishes installed KiCad 10 format.
            with tempfile.TemporaryDirectory(dir=work) as tmp:
                raw = Path(tmp) / "raw.kicad_pcb"
                descriptions = [next(p.value(2) for p in n.all("property") if p.value() == "Description")
                                for n in Document(data).root.all("symbol")]
                if number != 12:
                    raw.write_bytes(board(root_uid, ids, number == 1, descriptions))
                    saved = run([python, "-I", "-c", "import pcbnew,sys; b=pcbnew.LoadBoard(sys.argv[1]); "
                                 "pcbnew.SaveBoard(sys.argv[2],b)", raw, Path(tmp) / "saved.kicad_pcb"],
                                cwd=tmp, timeout=30)
                    if saved.returncode:
                        raise RuntimeError(saved.stderr)
                    (folder / "fault.kicad_pcb").write_bytes((Path(tmp) / "saved.kicad_pcb").read_bytes())
            if number == 9:
                (folder / "reported-net-members.json").write_text(json.dumps(dict(
                    source="deliberately faulty analyzer input", nets={"/LEFT": [["J2", "1"]],
                                                                       "/RIGHT": [["J1", "1"]]}), indent=2) + "\n", encoding="utf-8")
            if number == 12:
                (folder / "required-check.json").write_text(json.dumps(dict(
                    required_tool="kicad-cli", scope="erc", environment={
                        "PCBAI_KICAD_CLI": "./intentionally-absent-kicad-cli"}), indent=2) + "\n", encoding="utf-8")
        before = hashes(folder)
        with tempfile.TemporaryDirectory(dir=work) as tmp:
            root = Path(tmp)
            shutil.copytree(folder, root / "project")
            state = root / "state"
            state.mkdir()
            engine = Engine([root / "project/fault.kicad_pro"], state)
            session = next(iter(engine.sessions.entries.values()))
            measured = {}
            try:
                checks = [("erc", "fault.kicad_sch", {})]
                if number != 12:
                    checks += [("drc", "fault.kicad_pcb", {}),
                               ("drc_parity", "fault.kicad_pcb", {"parity": True}),
                               ("board_stats", "fault.kicad_pcb", {})]
                for tool, doc, extra in checks:
                    measured[tool] = engine.call("drc" if tool == "drc_parity" else tool,
                                                 dict(session.target(doc), **extra))
                if number == 12:
                    previous = os.environ.get("PCBAI_KICAD_CLI")
                    try:
                        os.environ["PCBAI_KICAD_CLI"] = str(root / "intentionally-absent-kicad-cli")
                        measured["missing_tool_erc"] = engine.call("erc", session.target("fault.kicad_sch"))
                    finally:
                        if previous is None:
                            os.environ.pop("PCBAI_KICAD_CLI", None)
                        else:
                            os.environ["PCBAI_KICAD_CLI"] = previous
                output = work / f"{slug}-netlist.xml"
                exported = run([cli, "sch", "export", "netlist", root / "project/fault.kicad_sch",
                                "--format", "kicadxml", "--output", output], cwd=root, timeout=60)
                measured["netlist_export_exit"] = exported.returncode
                if exported.returncode:
                    raise RuntimeError(exported.stderr)
                xml = ET.parse(output).getroot()
                measured["native_net_members"] = {
                    n.attrib["name"]: sorted((p.attrib["ref"], p.attrib["pin"]) for p in n.findall("node"))
                    for n in xml.findall("./nets/net")}
                if number != 12:
                    drc_output = work / f"{slug}-drc.json"
                    drc_process = run([cli, "pcb", "drc", root / "project/fault.kicad_pcb", "--format", "json",
                                       "--severity-all", "--exit-code-violations", "--output", drc_output],
                                      cwd=root, timeout=120)
                    measured["drc_cli"] = dict(exit_code=drc_process.returncode, stdout=drc_process.stdout,
                                               stderr=drc_process.stderr,
                                               report=json.loads(drc_output.read_text(encoding="utf-8")))
                if number == 9:
                    measured["supplied_report"] = json.loads((folder / "reported-net-members.json").read_text(encoding="utf-8"))
                    measured["available_tool_names"] = sorted(d["name"] for d in engine.definitions)
                if number == 1 and (drc_process.returncode != 0 or not measured["drc"]["ok"] or
                                    measured["drc"].get("verified") != "drc_ok"):
                    raise RuntimeError("Fixture #1 not accepted: actual DRC is not clean")
            finally:
                engine.jobs.close()
            results[slug] = measured
            measured["source_before"] = before
            measured["source_after"] = hashes(folder)
            measured["source_preserved"] = measured["source_before"] == measured["source_after"]
            if not measured["source_preserved"]:
                raise RuntimeError("Fixture source changed during read-only measurement")
        (work / "result.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(slug, {k: (v.get("verified"), v.get("ok")) for k, v in measured.items() if isinstance(v, dict)}, flush=True)


if __name__ == "__main__":
    main()
