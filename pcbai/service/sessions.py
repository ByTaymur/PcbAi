import threading
from dataclasses import dataclass
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.kicad.files import digest, revision, within


@dataclass
class Session:
    id: str
    root: Path
    project: str
    lock: threading.RLock

    def target(self, document):
        within(self.root, document)
        return dict(session=self.id, document=document, revision=revision(self.root))

    def validate(self, document, expected=None):
        path = within(self.root, document)
        if path.suffix not in {".kicad_sch", ".kicad_pcb", ".kicad_pro"}:
            raise PcbAiError("invalid_document", "Document must be a schematic, PCB or project file")
        current = self.target(document)
        if expected is not None and expected != current["revision"]:
            raise PcbAiError("stale_revision", "Project changed; inspect it and create a new preview")
        return path, current


class Sessions:
    def __init__(self, projects):
        self.entries = {}
        for project in projects:
            path = Path(project).expanduser().resolve()
            if path.suffix != ".kicad_pro" or not path.is_file():
                raise PcbAiError("invalid_project", "Register an existing .kicad_pro file")
            identity = "s-" + digest(str(path).encode())[:16]
            self.entries[identity] = Session(identity, path.parent, path.name, threading.RLock())

    def get(self, session):
        if session not in self.entries:
            raise PcbAiError("unknown_session", "Select an explicitly registered session from pcbai_status")
        return self.entries[session]

    def describe(self):
        return [dict(id=s.id, root=str(s.root), project=s.project, mode="file",
                     revision=revision(s.root), documents=[p.relative_to(s.root).as_posix()
                     for p in sorted(s.root.rglob("*.kicad_*")) if p.suffix in {".kicad_sch", ".kicad_pcb"}])
                for s in self.entries.values()]
