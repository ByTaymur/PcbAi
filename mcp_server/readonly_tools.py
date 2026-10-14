"""Tools agents may run without asking: exactly the registry entries with readOnlyHint=true (plan AJ-2).

    python -m mcp_server.readonly_tools          -> JSON list on stdout
    python -m mcp_server.readonly_tools --write  -> vscode/pcbai-vscode/mcp_tools.json (bundled copy)
"""
import json
import sys
from pathlib import Path

from pcbai.tools.engine import Engine

BUNDLED = Path(__file__).resolve().parents[1] / "vscode" / "pcbai-vscode" / "mcp_tools.json"


def tool_definitions():
    """The service's tool list without a project or state folder; _definitions reads no instance state."""
    return Engine._definitions(None)


def read_only_tools(definitions=None):
    return sorted(d["name"] for d in (definitions or tool_definitions())
                  if d.get("annotations", {}).get("readOnlyHint") is True
                  and d.get("annotations", {}).get("destructiveHint") is not True)


def bundled_text():
    tools = [{"name": d["name"], "readOnlyHint": d["annotations"]["readOnlyHint"],
              "destructiveHint": d["annotations"]["destructiveHint"]} for d in tool_definitions()]
    note = "Generated from pcbai.tools.engine definitions; tests/test_mcp_setup.py keeps it in sync."
    return json.dumps({"note": note, "tools": tools}, indent=1, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        BUNDLED.write_text(bundled_text(), encoding="utf-8", newline="\n")
        print(BUNDLED)
    else:
        print(json.dumps(read_only_tools()))
