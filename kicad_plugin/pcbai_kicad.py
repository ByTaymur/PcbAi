"""PcbAi KiCad 10 IPC plugin. KiCad runs the entrypoints in the plugin's own venv with KICAD_API_SOCKET/TOKEN set.

The plugin only finds out which project the PCB editor has open (IPC API) and talks to the PcbAi service through
the checkout's stdlib client. It never edits the board: checks run on the saved files.
"""
import json
import os
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
TITLE = "PcbAi"


def message(text, error=False):
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, TITLE, 0x10 if error else 0x40)
    else:
        print(text, file=sys.stderr if error else sys.stdout)


def ask(text):
    if os.name == "nt":
        import ctypes
        return ctypes.windll.user32.MessageBoxW(None, text, TITLE, 0x4 | 0x20) == 6  # Yes/No, question
    return False


def pcbai_root():
    configured = os.environ.get("PCBAI_ROOT")
    location = Path(os.environ.get("APPDATA", Path.home() / ".config")) / "PcbAi/location.json"
    if configured:
        value = configured
    else:
        try:
            value = json.loads(location.read_text(encoding="utf-8"))["root"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("PcbAi konumu bulunamadı. PCBAI_ROOT ortamını ayarlayın veya "
                               "PcbAi deposunda python kicad_plugin/configure.py çalıştırın. "
                               f"Konum dosyası: {location}") from exc
    if not isinstance(value, str) or not value.strip() or not Path(value).is_absolute():
        raise RuntimeError("PcbAi konumu mutlak bir klasör yolu olmalı (PCBAI_ROOT veya location.json).")
    root = Path(value).resolve()
    if not all((root / name).is_file() for name in ("mcp_server/client.py", "pcbai/__init__.py")):
        raise RuntimeError(f"PcbAi deposu bulunamadı: {root}. PCBAI_ROOT veya {location} ayarını düzeltin.")
    return root


def current_project():
    from kipy import KiCad
    board = KiCad(client_name="pcbai").get_board()
    doc = board.document
    folder = Path(doc.project.path)
    project = (folder / f"{doc.project.name}.kicad_pro").resolve()
    if not project.is_file():
        raise RuntimeError(f"Kart bir KiCad projesine bağlı değil (beklenen: {project}). Kartı proje içinden açın.")
    return project, (folder / doc.board_filename).resolve()


def client_for(project):
    root = pcbai_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from mcp_server.client import Client

    os.environ["PCBAI_PROJECTS"] = json.dumps([str(project)])
    client = Client()
    client.client_name = "kicad"
    try:
        client.connect()
        return client
    except RuntimeError as exc:
        if "different registered projects" not in str(exc):
            raise
    # A service is running without this project. Restart it with every project it had plus this one.
    health = client._request("GET", "/health", timeout=2)
    projects = sorted(set(health.get("projects", [])) | {str(project)})
    if not ask("PcbAi servisi bu projeyi tanımıyor. Servis bu projeyle birlikte yeniden başlatılsın mı?\n"
               "Ajanların bekleyen önizlemeleri silinir.\n\n" + "\n".join(projects)):
        raise RuntimeError("İptal edildi")
    client.shutdown()
    for _ in range(50):
        try:
            client.info = json.loads((client.state / "service.json").read_text(encoding="utf-8"))
            client._request("GET", "/health", timeout=1)
            time.sleep(0.1)
        except (OSError, ValueError, KeyError):
            break
    os.environ["PCBAI_PROJECTS"] = json.dumps(projects)
    client = Client()
    client.client_name = "kicad"
    client.connect()
    return client


def session_for(client, project):
    status = client.request("POST", "/call", {"name": "pcbai_status", "arguments": {}})
    for session in status.get("sessions", []):
        if os.path.normcase(str(Path(session["root"]) / session["project"])) == os.path.normcase(str(project)):
            return session
    raise RuntimeError("Servis bu projeyi kaydetmedi")


def run(action):
    try:
        action()
    except Exception as exc:  # the plugin has no console: every failure must reach the user as a dialog
        if str(exc) != "İptal edildi":
            hint = ("\n\nKiCad eklenti bağımlılıklarını kuramadı. İlk kurulum internet ister; "
                    "ağ erişimini ve KiCad'in eklenti Python ortamını kontrol edin."
                    if isinstance(exc, ModuleNotFoundError) and exc.name and exc.name.split('.')[0] == 'kipy'
                    else "")
            message(f"{exc}{hint}\n\n{traceback.format_exc(limit=3)}", error=True)
