"""Conservative structural model binding, independent of simulation success."""
import re
import xml.etree.ElementTree as ET

from pcbai.core.contract import PcbAiError
from pcbai.sch.scene import parse_netlist

NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:meg|[tgkmunpf])?(?:ohm|f|h)?$", re.I)
ACTIVE_LIBS = ("amplifier", "regulator", "transistor", "mcu", "driver", "interface", "timer", "comparator")


def inventory(xml):
    parsed = parse_netlist(xml)
    root = ET.fromstring(xml)
    answer, seen = [], set()
    connected = {reference for reference, _ in parsed["pins"]}
    for comp in root.iter("comp"):
        ref = comp.get("ref")
        if not ref or ref.casefold() in seen:
            raise PcbAiError("invalid_report", "Component references are missing or ambiguous")
        seen.add(ref.casefold())
        library = comp.find("libsource")
        lib = (library.get("lib", "") + ":" + library.get("part", "")) if library is not None else ""
        active = ref[:1].upper() in {"U", "Q", "D", "M"} or lib.casefold().startswith(ACTIVE_LIBS)
        answer.append(dict(reference=ref, active=active, connected=ref in connected, lib_id=lib))
    return answer


def coverage(parts, lines):
    """Bound means supported instance/model structure; pin order/physics remain unverified.

    All physical components stay in the denominator, including omitted or disconnected ones.
    Inner subcircuit devices never count as schematic references. Conditional definitions
    cannot establish binding without evaluating user expressions, so remain unbound.
    """
    if len(parts) > 10000 or len(lines) > 200000:
        raise PcbAiError("invalid_report", "Model coverage exceeds the component/line limit")
    refs = {}
    for part in parts:
        key = part["reference"].casefold()
        if key in refs:
            raise PcbAiError("invalid_report", "Ambiguous coverage reference")
        refs[key] = part
    models, subcircuits, instances = {}, {}, []
    current, ended = None, False
    conditional = any(re.match(r"^\s*\.(?:if|elseif|else|endif)(?=\s|\(|$)", line, re.I) for line in lines)
    for index, line in enumerate(lines):
        words = line.strip().split()
        if not words or words[0].startswith("*") or index == 0:
            continue
        if ended:
            raise PcbAiError("invalid_report", "Meaningful SPICE data follows the end of the deck")
        word = words[0].casefold()
        if word == ".end":
            if current is not None:
                raise PcbAiError("invalid_report", "Deck ends inside a subcircuit")
            ended = True
        elif word == ".subckt":
            if current is not None or len(words) < 3 or words[1].casefold() in subcircuits:
                raise PcbAiError("invalid_report", "Ambiguous or nested subcircuit declaration")
            header = []
            for token in words[2:]:
                if "=" in token or token.casefold().startswith("params:"):
                    break
                header.append(token)
            current = words[1].casefold()
            subcircuits[current] = dict(pins=header, instances=[])
        elif word == ".ends":
            if current is None or (len(words) > 1 and words[1].casefold() != current):
                raise PcbAiError("invalid_report", "Unmatched subcircuit end")
            current = None
        elif word == ".model":
            if len(words) < 3 or (current, words[1].casefold()) in models:
                raise PcbAiError("invalid_report", "Ambiguous model declaration")
            models[(current, words[1].casefold())] = words[2].split("(", 1)[0].casefold()
        elif word.startswith("."):
            continue
        else:
            (subcircuits[current]["instances"] if current else instances).append(words)
    if current is not None:
        raise PcbAiError("invalid_report", "Unterminated subcircuit declaration")

    resolutions = {}

    def binding(words, stack=()):
        kind = words[0][:1].upper()
        if conditional:
            return False, "conditional_netlist", None
        if kind in {"R", "C", "L"}:
            return (True, "ideal_primitive", None) if len(words) == 4 and NUMBER.fullmatch(words[3]) else (False, "unsupported_passive_expression", None)
        if kind in {"V", "I"}:
            ok = len(words) >= 4 and (NUMBER.fullmatch(words[3]) or words[3].casefold() in {"dc", "ac"}
                                     or words[3].casefold().startswith(("pulse(", "sin(", "pwl(", "exp(")))
            return bool(ok), "source_primitive" if ok else "unsupported_source", None
        if kind in {"E", "G", "F", "H"}:
            ok = len(words) >= (6 if kind in {"E", "G"} else 5)
            return ok, "controlled_source" if ok else "invalid_device_arity", None
        if kind == "X":
            args = []
            for token in words[1:]:
                if "=" in token or token.casefold().startswith("params:"):
                    break
                args.append(token)
            name = args[-1].casefold() if args else ""
            sub = subcircuits.get(name)
            if sub is None:
                return False, "missing_subcircuit", name
            if len(args) - 1 != len(sub["pins"]):
                return False, "model_pin_count_mismatch", name
            if name in stack or len(stack) >= 16:
                return False, "recursive_subcircuit", name
            key = (name, len(stack))
            if key not in resolutions:
                resolved = bool(sub["instances"]) and all(binding(row, (*stack, name))[0] for row in sub["instances"])
                resolutions[key] = resolved
            return resolutions[key], "declared_subcircuit" if resolutions[key] else "unsupported_subcircuit_body", name
        model_index = {"D": 3, "Q": 4, "J": 4, "M": 5}.get(kind)
        if model_index is None:
            return False, "unsupported_device", None
        if len(words) <= model_index:
            return False, "invalid_device_arity", None
        name = words[model_index].casefold()
        model = models.get((stack[-1] if stack else None, name), models.get((None, name)))
        allowed = {"D": {"d"}, "Q": {"npn", "pnp"}, "J": {"njf", "pjf"}, "M": {"nmos", "pmos", "vdmos"}}[kind]
        if not model:
            return False, "missing_or_local_model", name
        return model in allowed, "declared_model" if model in allowed else "model_type_mismatch", name

    matched, extras, seen_instances = {}, [], set()
    for words in instances:
        name = words[0].casefold()
        if name in seen_instances:
            raise PcbAiError("invalid_report", "Duplicate top-level SPICE instance")
        seen_instances.add(name)
        candidates = {key for key in (name, name[1:]) if key in refs}
        if len(candidates) > 1:
            raise PcbAiError("invalid_report", "SPICE instance has ambiguous physical reference")
        if not candidates:
            extras.append(words[0])
            continue
        key = candidates.pop()
        if key in matched:
            raise PcbAiError("invalid_report", "Several SPICE instances map to one physical component")
        matched[key] = dict(zip(("bound", "reason", "model"), binding(words), strict=True), instance=words[0])
    bindings = []
    for key, part in sorted(refs.items()):
        bindings.append(dict(part, **matched.get(key, dict(bound=False, reason="not_in_spice_netlist", model=None, instance=None))))
    bound = [r["reference"] for r in bindings if r["bound"]]
    unbound = [r["reference"] for r in bindings if not r["bound"]]
    active_bound = [r["reference"] for r in bindings if r["active"] and r["bound"]]
    active_unbound = [r["reference"] for r in bindings if r["active"] and not r["bound"]]
    return dict(bound=bound, unbound=unbound, ratio=len(bound) / len(bindings) if bindings else None,
                active_bound=active_bound, active_unbound=active_unbound,
                active_ratio=len(active_bound) / (len(active_bound) + len(active_unbound)) if active_bound or active_unbound else None,
                no_active_devices=not (active_bound or active_unbound), bindings=bindings,
                unmatched_spice_instances=extras, kind="structural_binding", pins_verified=False,
                models_physically_verified=False, active_classification="reference_prefix_or_library_category")


def meets_threshold(report, minimum):
    return minimum is None or report["ratio"] is not None and report["ratio"] >= minimum
