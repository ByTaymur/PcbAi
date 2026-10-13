"""Read-only KiCad SWIG oracle for S11. Run with KiCad Python -I."""
import json
import sys

import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
footprints = list(board.GetFootprints())
tracks = list(board.GetTracks())
pads = [p for fp in footprints for p in fp.Pads()]
print(json.dumps(dict(
    footprints=len(footprints), pads=len(pads),
    vias=sum(isinstance(t, pcbnew.PCB_VIA) for t in tracks),
    track_segments=sum(type(t) is pcbnew.PCB_TRACK for t in tracks),
    track_arcs=sum(isinstance(t, pcbnew.PCB_ARC) for t in tracks),
    zones=len(list(board.Zones())),
    nets={str(k): v.GetNetname() for k, v in board.GetNetsByNetcode().items() if v.GetNetname()},
    pad_members=sorted((fp.GetReference(), p.GetNumber(), p.GetNetname()) for fp in footprints for p in fp.Pads()),
    copper_layers=board.GetCopperLayerCount(), thickness_mm=pcbnew.ToMM(board.GetDesignSettings().GetBoardThickness()),
)))
