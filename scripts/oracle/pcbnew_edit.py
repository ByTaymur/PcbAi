"""Runs inside KiCad's own Python (pcbnew). Applies one operation per footprint and saves: a test oracle.

usage: python pcbnew_edit.py <in.kicad_pcb> <out.kicad_pcb> <ops.json>
ops.json: [{"reference": "R1", "x": mm|null, "y": mm|null, "rotation": deg|null, "side": "front"|"back"|null}]
Order per footprint: flip (left-right about its position), then absolute rotation, then position.
"""
import json
import sys

import pcbnew


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    ops = json.loads(open(sys.argv[3], encoding="utf-8").read())
    for op in ops:
        fp = board.FindFootprintByReference(op["reference"])
        if fp is None:
            raise SystemExit("missing " + op["reference"])
        side = "back" if fp.GetLayer() == pcbnew.B_Cu else "front"
        if op.get("side") and op["side"] != side:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        if op.get("rotation") is not None:
            fp.SetOrientationDegrees(op["rotation"])
        if op.get("x") is not None or op.get("y") is not None:
            pos = fp.GetPosition()
            x = pcbnew.FromMM(op["x"]) if op.get("x") is not None else pos.x
            y = pcbnew.FromMM(op["y"]) if op.get("y") is not None else pos.y
            fp.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
    pcbnew.SaveBoard(sys.argv[2], board)


if __name__ == "__main__":
    main()
