"""Isolated real service backend for browser acceptance; never opens user boards or settings."""

import json
import secrets
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pcbai.external import find_kicad_cli
from pcbai.service.server import Server, handler
from pcbai.tools.engine import Engine


def main():
    root = Path(sys.argv[1]).resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith("pcbai-viewer-"):
        raise SystemExit("Test directory must be a dedicated temporary directory")
    demos = Path(find_kicad_cli()).parent.parent / "share/kicad/demos"
    projects = []
    names = sys.argv[2].split(",") if len(sys.argv) > 2 else ["ecc83", "interf_u", "pic_programmer"]
    if any(n not in {"ecc83", "interf_u", "pic_programmer", "complex_hierarchy", "video"} for n in names):
        raise SystemExit("Unknown demo")
    for demo in names:
        folder = root / demo
        shutil.copytree(demos / demo, folder)
        projects.append(next(folder.glob("*.kicad_pro")))
    state = root / "state"
    state.mkdir()
    engine = Engine(projects, state)
    token = secrets.token_urlsafe(32)
    server = Server(("127.0.0.1", 0), handler(engine, token, "browser-test"))
    (root / "backend.json").write_text(
        json.dumps(
            dict(port=server.server_port, token=token, state=str(state), sessions=engine.sessions.describe())
        ),
        encoding="utf-8",
    )
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        engine.jobs.close()
        server.server_close()


if __name__ == "__main__":
    import tempfile

    main()
