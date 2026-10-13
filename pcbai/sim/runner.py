"""Minimal SPICE runner: KiCad's own netlist, sanitised as untrusted data, simulated by KiCad's ngspice."""

import json
import math
import os
import re
import sys
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli, run
from pcbai.kicad.exports import command
from pcbai.kicad.files import within

ANALYSES = (".tran", ".ac", ".dc", ".op", ".noise", ".tf", ".disto", ".pz", ".sens", ".sp")
# Built-in device models only. XSPICE d_process/d_cosim can execute external processes; file-backed
# d_source/d_state and arbitrary code models are not accepted from schematic/library text.
SAFE_MODEL_TYPES = {"r", "c", "l", "d", "npn", "pnp", "nmos", "pmos", "njf", "pjf", "nmf", "pmf",
                    "sw", "csw", "ltra", "urc", "txl", "cpl", "vdmos"}


def ngspice_paths():
    """KiCad's bundled shared ngspice and code models; PCBAI_NGSPICE overrides the library path."""
    configured = os.environ.get("PCBAI_NGSPICE")
    cli = Path(find_kicad_cli())
    library = Path(configured) if configured else cli.parent / ("ngspice.dll" if os.name == "nt" else "libngspice.so")
    if not library.is_file():
        raise PcbAiError("missing_dependency", "KiCad's shared ngspice library was not found; set PCBAI_NGSPICE")
    models = cli.parent.parent / "lib" / "ngspice"
    return library, sorted(models.glob("*.cm")) if models.is_dir() else []


def export_spice(copy, document):
    output = copy / "pcbai-sim.cir"
    command([find_kicad_cli(), "sch", "export", "netlist", within(copy, document), "--format", "spice",
             "--output", output], copy)
    return output.read_text(encoding="utf-8", errors="replace")


def sanitize(text, allowed_roots):
    """Inline checked model data, so ngspice cannot reopen unchecked includes or execute control scripts."""
    warnings, analyses = [], []
    roots = [Path(r).resolve() for r in allowed_roots]
    safe = set(ANALYSES) | {".title", ".end", ".subckt", ".ends", ".model", ".param", ".func", ".global",
                            ".temp", ".options", ".option", ".ic", ".nodeset", ".meas", ".measure",
                            ".if", ".elseif", ".else", ".endif"}
    remaining = 16 * 1024 * 1024

    def expand(contents, parent=None, stack=(), section=None):
        nonlocal remaining
        remaining -= len(contents.encode("utf-8"))
        if remaining < 0 or len(stack) > 32:
            raise PcbAiError("unsafe_netlist", "Model include depth/size limit exceeded")
        logical = []
        for raw in contents.splitlines():
            if raw.lstrip().startswith("+") and logical:
                logical[-1] += " " + raw.lstrip()[1:]
            else:
                logical.append(raw.rstrip())
        if section is not None:
            selected, active, found = [], False, False
            for line in logical:
                words = line.strip().split()
                if len(words) == 2 and words[0].lower() == ".lib" and not words[1].startswith(('"', "'")):
                    active = words[1].casefold() == section.casefold()
                    found |= active
                elif words and words[0].lower() == ".endl":
                    active = False
                elif active:
                    selected.append(line)
            if not found:
                raise PcbAiError("unsafe_netlist", "Requested model library section is absent")
            logical = selected
        output, in_control = [], False
        for line in logical:
            words = line.strip().split(None, 1)
            word = words[0].lower() if words else ""
            if word == ".control":
                in_control = True
                warnings.append("Schematic/model .control block ignored (scripts are not executed)")
                continue
            if in_control:
                in_control = word != ".endc"
                continue
            if word in {".include", ".inc", ".lib"}:
                match = re.fullmatch(r'\s*\S+\s+(?:"([^"]+)"|\x27([^\x27]+)\x27|([^\s]+))(?:\s+([^\s]+))?\s*', line)
                if not match:
                    raise PcbAiError("unsafe_netlist", "Invalid model include")
                name = next(v for v in match.groups()[:3] if v is not None)
                path = Path(name)
                if not path.is_absolute() and parent is not None:
                    path = parent / path
                path = path.resolve() if path.is_absolute() else path
                if (not path.is_absolute() or not path.is_file() or not any(path.is_relative_to(r) for r in roots)
                        or path in stack or path.stat().st_size > remaining):
                    raise PcbAiError("unsafe_netlist", "Model include is outside allowed roots, cyclic or too large")
                try:
                    included = path.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    raise PcbAiError("unsafe_netlist", "Cannot read model data") from exc
                output.extend(expand(included, path.parent, (*stack, path), match.group(4)))
                continue
            if word.startswith(".") and word not in safe:
                raise PcbAiError("unsafe_netlist", f"Unsupported SPICE directive: {word}")
            # Code models and PWL sources can otherwise read arbitrary files even without .include.
            if word == ".model":
                model = re.match(r'\s*\.model\s+\S+\s+([A-Za-z_]+)', line, re.IGNORECASE)
                if model is None or model.group(1).lower() not in SAFE_MODEL_TYPES:
                    raise PcbAiError("unsafe_netlist", "External/code model types are not supported")
            if not word.startswith("*") and re.search(r'\b[A-Za-z_]*(?:file(?:name)?|path)\s*[=(]', line, re.IGNORECASE):
                raise PcbAiError("unsafe_netlist", "File-backed SPICE models are not supported")
            if word in ANALYSES:
                if parent is not None:
                    raise PcbAiError("unsafe_netlist", "Model files cannot supply simulation commands")
                analyses.append(word[1:])
            output.append(line)
        if in_control:
            raise PcbAiError("unsafe_netlist", "Unterminated .control block")
        return output

    lines = expand(text)
    if not analyses:
        raise PcbAiError("no_analysis", "The schematic has no simulation command (.tran, .ac, .dc, .op …)")
    if len(analyses) > 1:
        raise PcbAiError("ambiguous_analysis", "Exactly one simulation command is supported per run")
    return lines, warnings, analyses


def simulate_lines(lines, cwd, vectors=None, max_points=20000, timeout=120):
    library, models = ngspice_paths()
    request = dict(library=str(library), codemodels=[str(m) for m in models], netlist=lines,
                   commands=["run"],
                   vectors=vectors, max_points=max_points)
    process = run([sys.executable, "-m", "pcbai.sim.ngspice_worker"], cwd=cwd, timeout=timeout,
                  input_data=json.dumps(request), env=dict(os.environ, PYTHONPATH=str(Path(__file__).parents[2])))
    try:
        output = json.loads(process.stdout)
    except ValueError as exc:
        raise PcbAiError("simulation_failed", "ngspice worker crashed: " + (process.stderr or "")[-500:]) from exc
    if not output.get("ok"):
        raise PcbAiError("simulation_failed", f"ngspice: {output.get('error')} {output.get('message', '')}"
                         + " | " + " ".join(output.get("log", [])[-8:]))
    if output["errors"]:
        raise PcbAiError("simulation_failed", "ngspice reported errors: " + " | ".join(output["errors"][-5:]))
    return output


def summarize(vectors):
    """Per-vector min/max/final for real data; magnitude range for complex data. Non-finite points are counted."""
    summary = {}
    for name, vector in vectors.items():
        values = vector["values"]
        if isinstance(values, dict):
            magnitude = [math.hypot(a, b) for a, b in zip(values["real"], values["imag"], strict=True)
                         if a is not None and b is not None]
            summary[name] = dict(kind="complex", points=vector["length"], magnitude_min=min(magnitude, default=None),
                                 magnitude_max=max(magnitude, default=None))
        else:
            finite = [v for v in values if v is not None]
            summary[name] = dict(kind="real", points=vector["length"], min=min(finite, default=None),
                                 max=max(finite, default=None), final=finite[-1] if finite else None,
                                 nonfinite=len(values) - len(finite))
    return summary
