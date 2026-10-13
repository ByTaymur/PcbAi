"""User-configured executable discovery. Never accept executable paths in tools."""
import os
import shutil
import subprocess
from pathlib import Path

from pcbai.core.contract import PcbAiError


def find_program(name, variable, *, wsl=False):
    configured = os.environ.get(variable)
    if configured and configured.startswith("wsl:"):
        if not wsl:
            raise PcbAiError("invalid_config", f"{variable} does not support WSL")
        from pcbai.pcb.engines.wsl import parse_spec
        parse_spec(configured)
        return configured
    if configured:
        candidate = Path(configured).expanduser().resolve()
        if not candidate.is_file():
            raise PcbAiError("missing_dependency", f"{variable} does not point to an executable file")
        return str(candidate)
    found = shutil.which(name)
    if not found:
        raise PcbAiError("missing_dependency", f"{name} not found; configure {variable} and run pcbai doctor")
    return found


def find_freerouting():
    return find_program("freerouting-cli", "PCBAI_FREEROUTING")


def freerouting_command(executable, args):
    if Path(executable).suffix.lower() == ".jar":
        return [find_program("java", "PCBAI_JAVA"), "-jar", executable, *args]
    return [executable, *args]


def find_tracemaker(*, place=False):
    return find_program("tracemaker-place" if place else "tracemaker",
                        "PCBAI_TRACEMAKER_PLACE" if place else "PCBAI_TRACEMAKER", wsl=True)


def find_kicad_python():
    configured = os.environ.get("PCBAI_KICAD_PYTHON")
    if configured:
        return find_program("python", "PCBAI_KICAD_PYTHON")
    candidate = Path(find_kicad_cli()).parent / ("python.exe" if os.name == "nt" else "python3")
    if candidate.is_file():
        return str(candidate)
    return find_program("python3", "PCBAI_KICAD_PYTHON")


def find_kicad_cli():
    configured = os.environ.get("PCBAI_KICAD_CLI")
    if configured:
        candidate = Path(configured).expanduser().resolve()
        if not candidate.is_file():
            raise PcbAiError("missing_dependency", "PCBAI_KICAD_CLI does not point to a file")
        return str(candidate)
    found = shutil.which("kicad-cli")
    if found:
        return found
    base = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "KiCad"
    candidates = list(base.glob("*/bin/kicad-cli.exe")) if base.exists() else []
    if candidates:
        return str(sorted(candidates, key=lambda p: tuple(int(x) for x in p.parents[1].name.split(".")),
                          reverse=True)[0])
    raise PcbAiError("missing_dependency", "kicad-cli not found; configure PCBAI_KICAD_CLI")


def user_config_dir(cli):
    """The user's KiCad settings folder for this KiCad version (e.g. %APPDATA%/kicad/10.0)."""
    version = Path(cli).resolve().parents[1].name  # .../KiCad/10.0/bin/kicad-cli
    base = os.environ.get("KICAD_CONFIG_HOME")
    if base:
        return Path(base) / version, version
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home())) / "kicad" / version, version
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kicad" / version, version


def is_kicad_cli(executable):
    return Path(str(executable)).name.lower() in {"kicad-cli", "kicad-cli.exe"}


def private_kicad_config(cli, destination):
    """Copy the user's KiCad settings (files, library tables, colour themes) into a private config home.

    Measured on KiCad 10.0.4: every kicad-cli run rewrites system.working_dir in the user's kicad_common.json.
    Running against a copy keeps results identical (same libraries, variables, themes) and never writes the
    user's settings. The copy is read-only input for one call and discarded afterwards.
    """
    source, version = user_config_dir(cli)
    target = Path(destination) / version
    target.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        for entry in source.iterdir():
            if entry.is_file() and entry.stat().st_size <= 8 * 1024 * 1024:
                shutil.copyfile(entry, target / entry.name)
            elif entry.is_dir() and entry.name == "colors":
                shutil.copytree(entry, target / entry.name, dirs_exist_ok=True)
    # Measured: kicad-cli crashes (0xC0000005) when the config home has no library tables. A fresh KiCad copies
    # them from its template on first start; do the same for users who have none.
    template = Path(cli).resolve().parents[1] / "share" / "kicad" / "template"
    for table in ("fp-lib-table", "sym-lib-table"):
        if not (target / table).is_file() and (template / table).is_file():
            shutil.copyfile(template / table, target / table)
    return Path(destination)


def run(argv, *, cwd=None, timeout=120, input_data=None, env=None):
    if argv and is_kicad_cli(argv[0]) and "KICAD_CONFIG_HOME" not in (env or {}):
        import tempfile

        with tempfile.TemporaryDirectory(prefix="pcbai-kicadcfg-") as home:
            private = private_kicad_config(argv[0], home)
            merged = dict(env if env is not None else os.environ, KICAD_CONFIG_HOME=str(private))
            return _run(argv, cwd=cwd, timeout=timeout, input_data=input_data, env=merged)
    return _run(argv, cwd=cwd, timeout=timeout, input_data=input_data, env=env)


def _run(argv, *, cwd=None, timeout=120, input_data=None, env=None):
    try:
        return subprocess.run([str(x) for x in argv], cwd=cwd, timeout=timeout, shell=False,
                              input=input_data, env=env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except subprocess.TimeoutExpired as exc:
        def tail(data):
            return (data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data or "")[-4096:]
        raise PcbAiError("timeout", f"External command exceeded {timeout}s",
                         details=dict(stdout_tail=tail(exc.stdout), stderr_tail=tail(exc.stderr))) from exc
    except OSError as exc:
        raise PcbAiError("external_error", str(exc)) from exc
