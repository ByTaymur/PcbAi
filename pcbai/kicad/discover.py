"""Configured/local IPC discovery; endpoints are never supplied by tool arguments."""
import csv
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import run
from pcbai.kicad.files import digest, within


def endpoints():
    configured = os.environ.get("PCBAI_KICAD_SOCKETS")
    if configured:
        try:
            paths = json.loads(configured)
        except ValueError as exc:
            raise PcbAiError("invalid_config", "PCBAI_KICAD_SOCKETS must be a JSON list of local ipc:// endpoints") from exc
    elif os.environ.get("KICAD_API_SOCKET"):
        paths = [os.environ["KICAD_API_SOCKET"]]
    else:
        directory = Path(tempfile.gettempdir() if os.name == "nt" else "/tmp") / "kicad"
        paths = ["ipc://" + str(directory / "api.sock")]
        paths.extend("ipc://" + str(p) for p in sorted(directory.glob("api-*.sock")))
        if os.name == "nt":
            # Windows transports are named pipes, so secondary sockets may have
            # no filesystem entry. Derive only KiCad process PID endpoint names.
            process = run(["tasklist", "/fo", "csv", "/nh"], timeout=15)
            if process.returncode:
                raise PcbAiError("ipc_discovery_failed", "Cannot enumerate KiCad processes")
            for row in csv.reader(process.stdout.splitlines()):
                if len(row) > 1 and row[0].lower() in {"kicad.exe", "pcbnew.exe"} and row[1].isdigit():
                    paths.append("ipc://" + str(directory / f"api-{row[1]}.sock"))
    if (not isinstance(paths, list) or not paths or len(paths) > 16
            or any(not isinstance(p, str) or not p.startswith("ipc://") or len(p) > 4096 or "\0" in p for p in paths)):
        raise PcbAiError("invalid_config", "Configure 1–16 local ipc:// endpoints")
    return {"ipc-" + digest(p.encode())[:24]: p for p in dict.fromkeys(paths)}


def request(endpoint, operation, *, worker_env=None, **target):
    process = run([sys.executable, "-m", "pcbai.kicad.ipc_worker"], timeout=5,
                  env=worker_env,
                  input_data=json.dumps(dict(socket=endpoint, operation=operation, **target)))
    if process.returncode:
        raise PcbAiError("ipc_unavailable", "Read-only IPC worker failed")
    try:
        output = json.loads(process.stdout)
    except ValueError as exc:
        raise PcbAiError("ipc_unavailable", "Read-only IPC worker returned invalid data") from exc
    if not isinstance(output, dict) or not isinstance(output.get("ok"), bool):
        raise PcbAiError("ipc_unavailable", "Invalid IPC response")
    if not output["ok"]:
        raise PcbAiError(output.get("error", {}).get("code", "ipc_unavailable"), output.get("summary", "IPC unavailable"))
    return output


def discover(sessions):
    channels, unavailable = [], []
    for identity, endpoint in endpoints().items():
        try:
            output = request(endpoint, "discover")
            registered = []
            for record in output["documents"]:
                project = Path(record["project"]).resolve()
                for session in sessions.entries.values():
                    if project != session.root / session.project:
                        continue
                    try:
                        board = within(session.root, record["document"])
                    except PcbAiError:
                        continue
                    if board.suffix == ".kicad_pcb":
                        registered.append(dict(session=session.id, document=board.relative_to(session.root).as_posix()))
            channels.append(dict(endpoint_id=identity, registered_documents=registered,
                                 open_pcb_count=len(output["documents"]), trusted=False))
        except PcbAiError as exc:
            unavailable.append(dict(endpoint_id=identity, code=exc.code))
    return dict(channels=channels, unavailable=unavailable)


def inspect_board(session, document, endpoint_id, operation):
    # Identity chooses a discovered/configured local channel, not a path/URL.
    if not re.fullmatch(r"ipc-[0-9a-f]{24}", endpoint_id):
        raise PcbAiError("unknown_endpoint", "Select an endpoint_id from discover_ipc")
    configured = endpoints()
    if endpoint_id not in configured:
        raise PcbAiError("unknown_endpoint", "Endpoint is no longer available; discover again")
    path = within(session.root, document)
    if path.suffix != ".kicad_pcb":
        raise PcbAiError("invalid_document", "Live IPC reads require a PCB document")
    return request(configured[endpoint_id], operation, project=str(session.root / session.project), board=str(path))
