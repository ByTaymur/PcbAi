"""A genuine child process for portable engine pipeline tests; modifies only permitted candidate geometry."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pcbai.pcb.edit import plan_move  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["route", "place"])
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    data = args.source.read_bytes()
    if args.operation == "place":
        data = plan_move(data, "R1", 11, 12)["data"]
    else:
        via = (b'(via (at 8 8) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net 1) '
               b'(uuid "33333333-3333-4333-8333-333333333333"))')
        data = data[:-1] + b'\n' + via + b')'
    args.output.write_bytes(data)


if __name__ == "__main__":
    main()
