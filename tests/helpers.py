import json
from pathlib import Path


SCHEMATIC = b'''(kicad_sch (version 20250114) (generator "eeschema")
  (uuid "11111111-1111-4111-8111-111111111111")
  (paper "A4") (lib_symbols)
  (symbol (lib_id "Device:R") (at 10 20 0) (unit 1)
    (uuid "22222222-2222-4222-8222-222222222222")
    (property "Reference" "R1" (at 10 19 0))
    (property "Value" "10k" (at 10 21 0))))\r\n'''
PCB = b'''(kicad_pcb (version 20241229) (generator "pcbnew")
  (net 0 "") (net 1 "GND") (net 2 "+3V3")
  (footprint "Resistor_SMD:R_0603_1608Metric" (layer "F.Cu") (at 10 20 90)
    (property "Reference" "R1") (property "Value" "10k")))\n'''


def shared_schematic(*, multi_unit=False, foreign=False):
    # The property deliberately differs from instance references: it is display state.
    from pcbai.sexpr import Document
    doc = Document(SCHEMATIC)
    node = doc.root.child("symbol")
    physical = SCHEMATIC[node.start:node.end - 1].replace(b'"R1"', b'"STALE"')
    records = b'''(instances (project "Test"
      (path "/root/sheet-a" (reference "R203") (unit 1))
      (path "/root/sheet-b" (reference "R303") (unit 1)))'''
    if foreign:
        records += b'(project "Other" (path "/other/sheet" (reference "R903") (unit 1))))'
    else:
        records += b')'
    symbol = physical + records + b')'
    if multi_unit:
        symbol += symbol.replace(b'(unit 1)', b'(unit 2)').replace(b'22222222', b'33333333')
    return (SCHEMATIC[:node.start] + symbol + SCHEMATIC[node.end:]).replace(
        b'11111111-1111-4111-8111-111111111111', b'root')


def make_project(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    project = root / "Test.kicad_pro"
    project.write_text(json.dumps({}), encoding="utf-8")
    (root / "Test.kicad_sch").write_bytes(SCHEMATIC)
    (root / "Test.kicad_pcb").write_bytes(PCB)
    return project
