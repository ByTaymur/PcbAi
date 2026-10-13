"""Allowlisted TraceMaker CLI. GPL program stays outside PcbAi packages."""
from pcbai.core.contract import PcbAiError
from pcbai.external import find_tracemaker
from pcbai.pcb.engines.wsl import argv as wsl_argv, linux_path


ROUTE_OPTIONS = {"work", "time_seconds", "threads", "variants", "diff_pairs", "reroute", "component_rules",
                 "no_tracks_on", "widen_power", "stitch_vias"}
PLACE_OPTIONS = {"placement_mode", "scratch", "route_check"}


def build(operation, source, destination, options, timeout, *, home=None):
    if operation not in {"route", "place"}:
        raise PcbAiError("invalid_arguments", "Unknown TraceMaker operation")
    allowed = ROUTE_OPTIONS if operation == "route" else PLACE_OPTIONS
    if set(options) - allowed:
        raise PcbAiError("invalid_arguments", "Unsupported TraceMaker options")
    executable = find_tracemaker(place=operation == "place")
    path = linux_path if executable.startswith("wsl:") else str
    args = (["route"] if operation == "route" else []) + [path(source), "-o", path(destination)]
    deterministic = False
    if operation == "route":
        if "work" in options and "time_seconds" in options:
            raise PcbAiError("invalid_arguments", "Choose a work budget or a time budget")
        if "time_seconds" in options:
            args += ["--time", str(options["time_seconds"])]
        else:
            args += ["--work", str(options.get("work", 3000000))]
            deterministic = True
        args += ["--no-gpu", "--threads", str(options.get("threads", 1)),
                 "--variants", str(options.get("variants", 1))]
        for name in ("diff_pairs", "reroute", "widen_power"):
            if options.get(name):
                args.append("--" + name.replace("_", "-"))
        for name in ("component_rules", "stitch_vias"):
            if name in options:
                args += ["--" + name.replace("_", "-"), options[name]]
        if options.get("no_tracks_on"):
            args += ["--no-tracks-on", ",".join(options["no_tracks_on"])]
    else:
        args += ["--mode", options.get("placement_mode", "routable")]
        if options.get("scratch"):
            args.append("--scratch")
        if "route_check" in options:
            args += ["--route-check", str(options["route_check"])]
    full = wsl_argv(executable, args, timeout - 10, home=home) if executable.startswith("wsl:") else [executable, *args]
    return full, deterministic
