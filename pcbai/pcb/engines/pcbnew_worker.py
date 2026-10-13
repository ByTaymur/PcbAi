"""DSN/SES bridge; launched only with configured KiCad Python, against private copies."""
import json
import os
import sys


def main():
    print("pcbai bridge: importing pcbnew", file=sys.stderr, flush=True)
    import pcbnew
    request = json.loads(sys.stdin.read(16384))
    print("pcbai bridge: loading saved board", file=sys.stderr, flush=True)
    board = pcbnew.LoadBoard(request["source"])
    if board is None:
        raise RuntimeError("KiCad could not load the board")
    if request["operation"] == "export":
        print("pcbai bridge: exporting DSN", file=sys.stderr, flush=True)
        if not pcbnew.ExportSpecctraDSN(board, request["dsn"]):
            raise RuntimeError("DSN export failed")
    elif request["operation"] == "import":
        print("pcbai bridge: saving baseline", file=sys.stderr, flush=True)
        pcbnew.SaveBoard(request["baseline"], board)
        print("pcbai bridge: importing SES", file=sys.stderr, flush=True)
        if not pcbnew.ImportSpecctraSES(board, request["ses"]):
            raise RuntimeError("SES import failed")
        pcbnew.SaveBoard(request["output"], board)
    else:
        raise ValueError("Unknown bridge operation")
    print(json.dumps(dict(ok=True)), flush=True)
    # KiCad's embedded Python/native teardown can hang after SaveBoard. All file writes are complete;
    # this disposable process owns no live editor and needs no GUI/plugin atexit handlers.
    os._exit(0)


if __name__ == "__main__":
    main()
