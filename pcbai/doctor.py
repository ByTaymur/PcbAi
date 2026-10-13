import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

from pcbai import __version__
from pcbai.external import find_kicad_cli, run


def inspect():
    findings = {"pcbai": __version__, "python": {"path": sys.executable, "version": sys.version.split()[0]}}
    try:
        cli = find_kicad_cli()
        process = run([cli, "--version"], timeout=15)
        if process.returncode:
            raise RuntimeError(process.stderr.strip())
        version = process.stdout.strip()
        findings["kicad_cli"] = {"available": True, "path": cli, "version": version,
                                 "ipc_minimum_met": tuple(int(v) for v in version.split(".")[:3]) >= (10, 0, 6)}
        install = Path(cli).parent.parent
        findings["kicad_python"] = {"available": (install / "bin/python.exe").is_file(),
                                    "path": str(install / "bin/python.exe")}
        dlls = list(install.rglob("*ngspice*.dll"))
        findings["ngspice_dll"] = {"available": bool(dlls), "paths": [str(p) for p in dlls],
                                    "tested": False}
    except Exception as exc:
        findings["kicad_cli"] = {"available": False, "error": str(exc)}
    findings["kipy"] = {"available": importlib.util.find_spec("kipy") is not None, "live_tested": False}
    for name in ("node", "ollama"):
        path = (os.environ.get("PCBAI_NODE") if name == "node" else None) or shutil.which(name)
        if path and not Path(path).is_file():
            path = None
        findings[name] = {"available": bool(path), "path": path}
    from pcbai.pcb.engines import describe
    for engine in describe():
        findings[engine["engine"]] = engine
    launcher = shutil.which("wsl.exe")
    findings["wsl"] = {"available": bool(launcher), "path": launcher, "distributions": []}
    if launcher:
        try:
            import subprocess
            out = subprocess.run([launcher, "-l", "-q"], shell=False, timeout=15, capture_output=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            text = out.stdout.decode("utf-16-le" if b"\0" in out.stdout else "utf-8", errors="replace")
            findings["wsl"].update(distributions=[s.strip() for s in text.splitlines() if s.strip()]
                                    if out.returncode == 0 else [], returncode=out.returncode)
        except Exception as exc:
            findings["wsl"]["error"] = str(exc)
    config = Path(os.environ.get("APPDATA", Path.home() / ".config")) / "kicad/10.0/kicad_common.json"
    try:
        settings = json.loads(config.read_text(encoding="utf-8"))
        findings["ipc"] = {"enabled_in_user_config": settings.get("api", {}).get("enable_server", False),
                             "connected": False}
    except (OSError, ValueError):
        findings["ipc"] = {"enabled_in_user_config": None, "connected": False}
    return findings


if __name__ == "__main__":
    print(json.dumps(inspect(), ensure_ascii=False, indent=2))
