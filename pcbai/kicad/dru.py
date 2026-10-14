"""Custom DRC rule gate for ``<board>.kicad_dru``.

Measured on KiCad 10.0.4: ``kicad-cli pcb drc`` silently drops a .kicad_dru that does not compile and still
exits 0 with a report from the built-in rules (324 → 2 violations on ecc83-pp, no message). KiCad master fails
the job instead (exit 3), but that change is not on the 10.0 branch (Diode pcb PR #1381, 5 Oct 2026).
So a DRC with custom rules is trusted only when (1) the file passes a structural preflight here and
(2) a separate DRC run proves KiCad loaded the file: a probe rule appended to the same file must fire.
A rule that KiCad drops on its own (for example a bad condition expression) is not detected; that limit is
reported, never hidden.
"""

import re
import secrets

from pcbai.core.contract import PcbAiError
from pcbai.sexpr import Document

LENGTH_CONSTRAINTS = {
    "annular_width", "clearance", "connection_width", "courtyard_clearance", "creepage", "diff_pair_gap",
    "diff_pair_uncoupled", "edge_clearance", "hole_clearance", "hole_size", "hole_to_hole", "length",
    "physical_clearance", "physical_hole_clearance", "silk_clearance", "text_height", "text_thickness",
    "thermal_relief_gap", "thermal_spoke_width", "track_width", "via_diameter",
}
RULE_CLAUSES = {"constraint", "condition", "layer", "severity"}
_NUMBER = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)$")
_LINE_COMMENT = re.compile(r'^\s*#.*$', re.MULTILINE)



def preflight(data):
    """Return {rules, problems}; problems are strings with a rule name or line. No KiCad call."""
    if len(data) > 4 * 1024 * 1024:
        return dict(rules=0, problems=["rules file exceeds 4 MiB"])
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return dict(rules=0, problems=["rules file is not UTF-8"])
    stripped = _LINE_COMMENT.sub("", text)
    if not stripped.strip():
        return dict(rules=0, problems=[])
    try:
        root = Document(("(pcbai_rules\n" + stripped + "\n)").encode()).root
    except PcbAiError as exc:
        return dict(rules=0, problems=[f"not a complete S-expression: {exc}"])
    problems, rules, names = [], 0, set()
    forms = [n for n in root.children[1:] if n.atom is None]
    if len(forms) != len(root.children) - 1:
        problems.append("text outside (version …) and (rule …) forms")
    versions = [f for f in forms if f.name == "version"]
    if len(versions) != 1:
        problems.append("expected exactly one (version 1)")
    for form in forms:
        if form.name == "version":
            continue
        if form.name != "rule":
            problems.append(f"unknown top-level form ({form.name} …)")
            continue
        rules += 1
        name = form.value(1)
        label = f'rule "{name}"' if isinstance(name, str) else f"rule #{rules}"
        if not isinstance(name, str) or not name:
            problems.append(f"{label}: missing name")
        elif name in names:
            problems.append(f"{label}: duplicate name")
        names.add(name)
        clauses = [c for c in form.children[2:] if c.atom is None]
        if len(clauses) != len(form.children) - 2:
            problems.append(f"{label}: stray atom inside rule")
        constraints = [c for c in clauses if c.name == "constraint"]
        if not constraints:
            problems.append(f"{label}: no (constraint …)")
        for clause in clauses:
            if clause.name not in RULE_CLAUSES:
                problems.append(f"{label}: unknown clause ({clause.name} …)")
            if clause.name == "condition":
                expression = clause.value(1)
                if not isinstance(expression, str) or expression.count("(") != expression.count(")") \
                        or expression.count("'") % 2:
                    problems.append(f"{label}: condition is not a balanced quoted expression")
        for constraint in constraints:
            kind = constraint.value(1)
            if kind in LENGTH_CONSTRAINTS:
                for bound in constraint.children[2:]:
                    if bound.atom is None and bound.name in {"min", "max", "opt"}:
                        value = bound.value(1)
                        if isinstance(value, str) and _NUMBER.match(value):
                            problems.append(f"{label}: {kind} {bound.name} {value} has no unit (KiCad drops it)")
    return dict(rules=rules, problems=problems)


def probe_rules(data):
    """The original rules plus one rule that must fire on any board with copper: (name, bytes)."""
    name = "pcbai_probe_" + secrets.token_hex(6)
    probe = (f'\n(rule "{name}"\n  (constraint clearance (min 1000mm))\n  (constraint edge_clearance (min 1000mm)))\n')
    body = data.decode("utf-8") if data.strip() else "(version 1)\n"
    return name, (body.rstrip() + "\n" + probe).encode("utf-8")
