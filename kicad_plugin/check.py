from assistant_core import check_lines
from pcbai_kicad import client_for, current_project, message, run, session_for


def check():
    """One verdict with VS Code and MCP: the service's aggregate check (ignored required rules, waivers, coverage)."""
    project, _board = current_project()
    client = client_for(project)
    session = session_for(client, project)
    response = client.request("POST", "/call", {"name": "check", "arguments": {"session": session["id"], "scope": "all"}})
    message("\n".join(check_lines(response)))


run(check)
