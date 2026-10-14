import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

from pcbai import __version__
from pcbai.external import find_kicad_cli, run


# Supported KiCad: 10.0 branch from 10.0.7 (latest stable bug-fix release, 7 Oct 2026; IPC flip_items needs
# ≥ 10.0.6). 11.x is not yet supported. Every 10.0.x drops a malformed .kicad_dru silently and exits 0, so DRC
# with custom rules always goes through pcbai.kicad.dru's gate; a newer KiCad does not remove that gate.
KICAD_MINIMUM = (10, 0, 7)
KICAD_SERIES = (10, 0)


def kicad_version_tuple(text):
    parts = []
    for piece in text.split("-")[0].split(".")[:3]:
        if not piece.isdigit():
            return None
        parts.append(int(piece))
    return tuple(parts + [0] * (3 - len(parts)))


def requirements(findings):
    """Unmet hard requirements as readable strings; empty means PcbAi may run its checks."""
    unmet = []
    cli = findings.get("kicad_cli", {})
    if not cli.get("available"):
        unmet.append("kicad-cli bulunamadı: KiCad 10.0.7 veya sonraki 10.0.x kurun")
    elif not cli.get("supported"):
        unmet.append(f"KiCad {cli.get('version')} desteklenmiyor: 10.0.7 veya sonraki 10.0.x gerekir "
                     "(https://www.kicad.org/download/)")
    return unmet


def inspect():
    findings = {"pcbai": __version__, "python": {"path": sys.executable, "version": sys.version.split()[0]}}
    try:
        cli = find_kicad_cli()
        process = run([cli, "--version"], timeout=15)
        if process.returncode:
            raise RuntimeError(process.stderr.strip())
        version = process.stdout.strip()
        parsed = kicad_version_tuple(version)
        findings["kicad_cli"] = {"available": True, "path": cli, "version": version,
                                 "minimum": ".".join(map(str, KICAD_MINIMUM)),
                                 "supported": parsed is not None and parsed[:2] == KICAD_SERIES
                                 and parsed >= KICAD_MINIMUM,
                                 "ipc_minimum_met": parsed is not None and parsed >= (10, 0, 6),
                                 "custom_rules_gate": "probe"}
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
    from pcbai.external import find_program
    variable = "PCBAI_PCB_DFM_PYTHON" if os.environ.get("PCBAI_PCB_DFM_PYTHON") else "PCBAI_PCB_DFM"
    try:
        path = find_program("python" if variable.endswith("PYTHON") else "pcb-dfm", variable)
        findings["pcb_dfm"] = dict(available=True, path=path, configuration=variable,
                                    separate_process=True, dependency_import_verified=False, production_verified=False)
    except Exception as exc:
        findings["pcb_dfm"] = dict(available=False, configuration=variable, error=str(exc), separate_process=True)
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
    findings["requirements_unmet"] = requirements(findings)
    return findings


if __name__ == "__main__":
    print(json.dumps(inspect(), ensure_ascii=False, indent=2))
