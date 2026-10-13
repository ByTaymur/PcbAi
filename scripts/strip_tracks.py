"""Strip route copper only, from a COPY; command output is restricted to .pcbai-state."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pcbai.kicad.board import board  # noqa: E402
from pcbai.pcb.edit import Edits  # noqa: E402
from scripts.evidence_output import report_path  # noqa: E402


def strip_tracks(data):
    edits = Edits(data)
    for node in board(data).children:
        if node.name in {"segment", "arc", "via"}:
            edits.changes.append((node.start, node.end, b""))
    return edits.result()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = report_path(ROOT, args.output.name, output=args.output)
    if args.source.resolve() == output:
        parser.error("Input and output must be distinct")
    output.write_bytes(strip_tracks(args.source.read_bytes()))
    print(output)


if __name__ == "__main__":
    main()
