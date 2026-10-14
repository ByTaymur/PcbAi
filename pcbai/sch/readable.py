"""Readable netlist text for agents, built only from KiCad's own netlist (R3-A1).

Format idea from tscircuit/circuit-json-to-readable-netlist (MIT): nets grouped, one line per pin with a short
description. Nothing is inferred: pin names, pin types, values and parts are copied from the netlist, and file
text is treated as data (control characters and line breaks are removed so a field cannot forge a NET line).
"""

import re

from pcbai.core.contract import PcbAiError

POWER_TYPES = {"power_in", "power_out"}
LARGE_NET = 12
FIELD_CHARS = 48
NAME_CHARS = 256
_UNSAFE = re.compile("[\\x00-\\x1f\\x7f\\u2028\\u2029]+")


def clean(text, limit=FIELD_CHARS):
    """One-line, bounded copy of untrusted netlist text. Names (net, reference, pin) use NAME_CHARS."""
    text = _UNSAFE.sub(" ", str(text or "")).strip()
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _pin_key(member):
    pin = member["pin"] or ""
    return (member["reference"] or "", 0, int(pin), "") if pin.isdigit() else (member["reference"] or "", 1, 0, pin)


def _is_power(members):
    return any(m.get("type") in POWER_TYPES for m in members)


def _is_unconnected(name, members):
    return len(members) == 1 and name.startswith("unconnected-")


def readable_netlist(netlist, *, nets=None, max_chars=12000, expand_large=False, include_unconnected=False):
    """Text netlist plus counts. Raises unknown_net for a requested net that does not exist."""
    members = netlist["members"]
    components = netlist["components"]
    if nets:
        missing = sorted(set(nets) - set(members))
        if missing:
            raise PcbAiError("unknown_net", "Nets not in this netlist: " + ", ".join(clean(n) for n in missing[:10]))
        selected = list(dict.fromkeys(nets))
    else:
        selected = [n for n in members if include_unconnected or not _is_unconnected(n, members[n])]
        # Signal nets first by name, then power/ground; the agent reads the circuit before the rails.
        selected.sort(key=lambda n: (_is_power(members[n]), n))
    skipped_unconnected = sum(1 for n in members if _is_unconnected(n, members[n])) if not (nets or include_unconnected) else 0
    blocks, summarized = [], []
    for name in selected:
        pins = sorted(members[name], key=_pin_key)
        parts = sorted({p["reference"] for p in pins})
        power = _is_power(pins)
        head = f"NET {clean(name, NAME_CHARS)}  ({len(pins)} pins{', power' if power else ''})"
        if len(pins) > LARGE_NET and not expand_large and not nets:
            shown = ", ".join(clean(r, NAME_CHARS) for r in parts[:8]) + (f", +{len(parts) - 8}" if len(parts) > 8 else "")
            blocks.append(f"{head}\n  {len(parts)} components: {shown}")
            summarized.append(name)
            continue
        lines = [head]
        for pin in pins:
            comp = components.get(pin["reference"], {})
            function = clean(pin.get("function")) or "~"
            kind = clean(pin.get("type")) or "?"
            describe = clean(comp.get("value"))
            if comp.get("part") and clean(comp["part"]) != describe:
                describe = f"{describe} [{clean(comp['part'])}]" if describe else f"[{clean(comp['part'])}]"
            lines.append(f"  {clean(pin['reference'], NAME_CHARS)}.{clean(pin['pin'], NAME_CHARS)}  {function}  ({kind})  {describe}".rstrip())
        blocks.append("\n".join(lines))
    text, used, written = [], 0, 0
    for block in blocks:
        if used + len(block) + 1 > max_chars:
            break
        text.append(block)
        used += len(block) + 1
        written += 1
    return dict(text="\n".join(text), nets_total=len(members), nets_written=written,
                nets_omitted=len(blocks) - written, truncated=written < len(blocks),
                summarized_nets=summarized[:256], unconnected_skipped=skipped_unconnected,
                components=len([r for r in components if not r.startswith("#")]))
