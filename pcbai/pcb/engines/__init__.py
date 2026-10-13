"""Optional route/placement engine inventory and isolated execution."""
import os
import re
import tempfile
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_freerouting, find_tracemaker, freerouting_command, run
from pcbai.kicad.files import digest
from pcbai.pcb.engines.base import run_process
from pcbai.pcb.engines.wsl import argv as wsl_argv, parse_spec


def describe():
    engines = []
    for name, finder in (("freerouting", find_freerouting), ("tracemaker", find_tracemaker)):
        try:
            path = finder()
            wsl = path.startswith("wsl:")
            flag = "--help" if name == "freerouting" else "--version"
            with tempfile.TemporaryDirectory(prefix="pcbai-engine-info-") as tmp:
                command = wsl_argv(path, [flag], 10, home=tmp) if wsl else [path, flag]
                if name == "freerouting":
                    command = freerouting_command(path, [flag, "--user_data_path=" + tmp, "-l", "en", "-da"])
                env = dict(os.environ, APPDATA=tmp, LOCALAPPDATA=tmp, HOME=tmp, XDG_CONFIG_HOME=tmp)
                process = run(command, cwd=tmp, timeout=15, env=env)
            if process.returncode:
                raise PcbAiError("engine_unavailable", (process.stderr or process.stdout)[-500:])
            output = (process.stdout or process.stderr).strip()
            version_match = re.search(r"(?:Freerouting (?:CLI )?v|[Vv]ersion\s+|TraceMaker\s+v?)(\d+\.\d+\.\d+)", output)
            info = dict(engine=name, available=True, path=path, via="wsl" if wsl else "native",
                        version=version_match.group(1) if version_match else output[:200], commit=None,
                        deterministic_supported=name == "tracemaker", tested=False, cpu_only=name == "tracemaker")
            if wsl:
                info["distro"] = parse_spec(path)[0]
            if name == "tracemaker":
                try:
                    info["placement_path"] = find_tracemaker(place=True)
                except PcbAiError:
                    info["placement_path"] = None
            engines.append(info)
        except PcbAiError as exc:
            engines.append(dict(engine=name, available=False, tested=False, error=str(exc), code=exc.code))
    return engines


def execute(state, data, engine, operation, options, timeout=150, *, project_data=None, rules_data=None):
    if engine not in {"freerouting", "tracemaker"} or operation not in {"route", "place"}:
        raise PcbAiError("invalid_arguments", "Unknown engine or operation")
    if engine == "freerouting" and operation == "place":
        raise PcbAiError("invalid_arguments", "Freerouting does not place components")
    directory = Path(state) / "engine-runs"
    directory.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="run-", dir=directory) as tmp:
        root = Path(tmp)
        source, destination = root / "in.kicad_pcb", root / "out.kicad_pcb"
        source.write_bytes(data)
        if project_data is not None:
            (root / "in.kicad_pro").write_bytes(project_data)
        if rules_data is not None:
            (root / "in.kicad_dru").write_bytes(rules_data)
        if engine == "tracemaker":
            from pcbai.pcb.engines.tracemaker import build
            # Prevent implicit per-user/project TraceMaker configs/knowledge bases entering a run.
            home = root / "home"
            home.mkdir()
            command, deterministic = build(operation, source, destination, options, timeout, home=home)
            env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / "config"),
                       XDG_CACHE_HOME=str(home / "cache"))
            outcome = run_process(command, cwd=root, timeout=timeout, env=env)
            outcome["deterministic"] = deterministic
            if outcome["returncode"] not in {0, 1}:
                raise PcbAiError("engine_failed", "TraceMaker failed: " + outcome["stderr_tail"])
        else:
            from pcbai.pcb.engines.freerouting import route
            outcome = route(source, destination, options, timeout)
        if (not destination.exists() or destination.is_symlink() or getattr(destination.lstat(), "st_file_attributes", 0) & 0x400
                or not destination.is_file() or not 0 < destination.stat().st_size <= 64 * 1024 * 1024):
            raise PcbAiError("engine_failed", "Engine output is missing, linked, empty or too large")
        changed = destination.read_bytes()
        if source.read_bytes() != data:
            raise PcbAiError("engine_touched_foreign_items", "Engine modified its input file")
        outcome.update(engine=engine, operation=operation, input_sha256=digest(data), output_sha256=digest(changed))
        # Version belongs to this exact executable, not an inferred release/default selection.
        outcome["version"] = next((e.get("version") for e in describe() if e["engine"] == engine), None)
        outcome["commit"] = None
        return changed, outcome
