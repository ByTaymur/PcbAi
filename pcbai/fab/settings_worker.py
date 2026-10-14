"""Trusted native settings reader. Run only on a private project snapshot."""
import json
import os
import sys


def main():
    import pcbnew
    board = pcbnew.LoadBoard(sys.argv[1])
    settings = board.GetDesignSettings()
    attributes = dict(min_clearance="m_MinClearance", min_track_width="m_TrackMinWidth",
                      min_through_hole_diameter="m_MinThroughDrill", min_via_annular_width="m_ViasMinAnnularWidth",
                      min_copper_edge_clearance="m_CopperEdgeClearance", min_text_height="m_MinSilkTextHeight",
                      min_text_thickness="m_MinSilkTextThickness", min_silk_clearance="m_SilkClearance")
    output = {key: pcbnew.ToMM(getattr(settings, name)) for key, name in attributes.items()}
    print(json.dumps(output, allow_nan=False), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(type(exc).__name__ + ": " + str(exc), file=sys.stderr, flush=True)
        os._exit(1)
    # Native wx teardown can hang; no native objects or project writes are needed.
    os._exit(0)
