"""DSN → external Freerouting → SES. Rebase verified route deltas onto original bytes."""
import json
import os
import sys
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_freerouting, find_kicad_python, freerouting_command, run
from pcbai.pcb.engines.base import run_process
from pcbai.pcb.engine_guard import rebase_routes


def bridge(directory, request):
    # pcbnew is allowed only in this subprocess, not imported by the PcbAi service.
    home = directory / "kicad-config"
    home.mkdir(exist_ok=True)
    from pcbai.external import find_kicad_cli, private_kicad_config
    private_kicad_config(find_kicad_cli(), home)
    env = dict(os.environ, KICAD_CONFIG_HOME=str(home))
    worker = Path(__file__).with_name("pcbnew_worker.py")
    process = run([find_kicad_python(), str(worker)], cwd=directory, timeout=60,
                  input_data=json.dumps(request), env=env)
    if process.returncode:
        raise PcbAiError("engine_failed", "KiCad DSN/SES bridge failed: " + process.stderr[-4096:])


def route(source, destination, options, timeout):
    if set(options) - {"passes", "threads"}:
        raise PcbAiError("invalid_arguments", "Freerouting supports passes and threads only")
    directory = source.parent
    dsn, ses = directory / "board.dsn", directory / "board.ses"
    bridge(directory, dict(operation="export", source=str(source), dsn=str(dsn)))
    executable = find_freerouting()
    args = ["-de", str(dsn), "-do", str(ses),
            "--router.autorouter.max_passes=" + str(options.get("passes", 5)),
            "--router.autorouter.max_threads=" + str(options.get("threads", 1)),
            "--router.optimizer.max_threads=" + str(options.get("threads", 1)),
            "--router.optimizer.max_passes=5", "--gui.enabled=false", "--api_server.enabled=false",
            "--mcp_server.enabled=false", "--usage_and_diagnostic_data.disable_analytics=true",
            "--user_data_path=" + str(directory / "config"), "--logging.file.enabled=false",
            "--feature_flags.save_jobs=false"]
    env = dict(os.environ, APPDATA=str(directory / "config"), LOCALAPPDATA=str(directory / "cache"),
               XDG_CONFIG_HOME=str(directory / "config"), XDG_CACHE_HOME=str(directory / "cache"))
    # Treat native Windows CLI as the executable. No Java/JAR command interpretation.
    outcome = run_process(freerouting_command(executable, args), cwd=directory, timeout=timeout, env=env)
    if outcome["returncode"] or not ses.is_file() or not ses.stat().st_size:
        raise PcbAiError("engine_failed", "Freerouting did not produce SES: " + outcome["stderr_tail"])
    baseline, routed = directory / "baseline.kicad_pcb", directory / "routed.kicad_pcb"
    bridge(directory, dict(operation="import", source=str(source), ses=str(ses), baseline=str(baseline),
                           output=str(routed)))
    destination.write_bytes(rebase_routes(source.read_bytes(), baseline.read_bytes(), routed.read_bytes()))
    return outcome | dict(deterministic=False, python=sys.version.split()[0])
