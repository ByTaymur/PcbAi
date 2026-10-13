"""Short-lived read-only kipy worker. stdin is JSON data, never executable code."""
import json
import sys
from pathlib import Path

from pcbai.core.contract import PcbAiError, error


def document_info(document):
    return dict(project=str(Path(document.project.path) / (document.project.name + ".kicad_pro")),
                document=document.board_filename)


def execute(request):
    from kipy import KiCad
    from kipy.proto.common.types import DocumentType
    client = KiCad(socket_path=request["socket"], client_name="pcbai-read-only", timeout_ms=1000)
    try:
        documents = list(client.get_open_documents(DocumentType.DOCTYPE_PCB))
        records = [document_info(d) for d in documents]
        if request["operation"] == "discover":
            return dict(ok=True, documents=records)
        if request["operation"] not in {"selection", "summary"}:
            raise PcbAiError("invalid_arguments", "Unknown IPC operation")
        # KiCad 10's public get_board() chooses docs[0]. Refuse that choice unless
        # exactly one document exists and its explicit project/document match.
        if len(records) != 1:
            raise PcbAiError("ambiguous_document", "IPC endpoint must contain exactly one PCB document")
        expected_project = Path(request["project"]).resolve()
        expected_board = Path(request["board"]).resolve()
        record = records[0]
        if Path(record["project"]).resolve() != expected_project:
            raise PcbAiError("wrong_target", "IPC endpoint is showing a different project")
        board_path = Path(record["document"])
        if not board_path.is_absolute():
            board_path = expected_project.parent / board_path
        if board_path.resolve() != expected_board:
            raise PcbAiError("wrong_target", "IPC endpoint is showing a different board")
        board = client.get_board()
        if document_info(board.document) != record:
            raise PcbAiError("wrong_target", "IPC document changed during selection")
        contents = board.get_as_string()
        if request["operation"] == "summary":
            output = dict(ok=True, contents=contents)
        else:
            from google.protobuf.json_format import MessageToDict
            items = [dict(type=type(item).__name__, data=MessageToDict(item.proto), trusted=False)
                     for item in board.get_selection()]
            if board.get_as_string() != contents:
                raise PcbAiError("stale_live_revision", "Live board changed while selection was read")
            output = dict(ok=True, contents=contents, selection=items)
        if [document_info(d) for d in client.get_open_documents(DocumentType.DOCTYPE_PCB)] != records:
            raise PcbAiError("wrong_target", "IPC document changed while being inspected")
        return output
    finally:
        # kipy 0.8.0 has no public close() on KiCad. Closing its transport keeps
        # discovery from retaining connections; process exit also closes handles.
        connection = getattr(client._client, "_conn", None)
        if connection is not None:
            connection.close()


def main():
    try:
        request = json.loads(sys.stdin.read(1024 * 1024))
        output = execute(request)
    except ImportError:
        output = error(PcbAiError("missing_dependency", "Install the optional ipc dependency (kicad-python)"))
    except PcbAiError as exc:
        output = error(exc)
    except Exception as exc:
        output = error(PcbAiError("ipc_unavailable", str(exc)))
    print(json.dumps(output, ensure_ascii=True, allow_nan=False))


if __name__ == "__main__":
    main()
