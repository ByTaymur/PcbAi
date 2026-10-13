"""Net class edits in the KiCad project file. Refuses when the JSON cannot be re-written byte-faithfully."""

import json

from pcbai.core.contract import PcbAiError
from pcbai.views import number

FIELDS = {"clearance_mm": "clearance", "track_width_mm": "track_width", "via_diameter_mm": "via_diameter",
          "via_drill_mm": "via_drill"}


def _dump(value, newline):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").replace("\n", newline).encode("utf-8")


def plan_netclass(data, name, values, patterns=()):
    """Create or update net class ``name`` with mm ``values``; optionally assign net name ``patterns``."""
    try:
        project = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise PcbAiError("invalid_document", "Project file is not valid JSON") from exc
    newline = "\r\n" if b"\r\n" in data else "\n"
    if _dump(project, newline) != data:
        raise PcbAiError("unsupported_edit", "Project JSON formatting would change; edit net classes in KiCad")
    if not isinstance(name, str) or not name.strip() or len(name) > 64 or any(ord(c) < 32 for c in name):
        raise PcbAiError("invalid_arguments", "Net class name must be 1–64 printable characters")
    settings = project.get("net_settings")
    if not isinstance(settings, dict) or not isinstance(settings.get("classes"), list):
        raise PcbAiError("invalid_document", "Project has no net class table")
    classes = settings["classes"]
    entry = next((c for c in classes if c.get("name") == name), None)
    created = entry is None
    if created:
        default = next((c for c in classes if c.get("name") == "Default"), None)
        if default is None:
            raise PcbAiError("invalid_document", "Project has no Default net class to copy")
        used = [c.get("priority") for c in classes if c.get("name") != "Default" and isinstance(c.get("priority"), int)]
        entry = dict(default, name=name, priority=max(used, default=-1) + 1)
        classes.append(entry)
    old = {k: entry.get(v) for k, v in FIELDS.items()}
    for key, field in FIELDS.items():
        if key in values:
            value = number(values[key])
            if not 0 <= value <= 25 or (field != "clearance" and value <= 0):
                raise PcbAiError("invalid_arguments", f"{key} is out of range")
            entry[field] = value
    if entry.get("via_drill", 0) >= entry.get("via_diameter", 1):
        raise PcbAiError("invalid_arguments", "Via drill must be smaller than via diameter")
    assigned = []
    if patterns:
        rules = settings.setdefault("netclass_patterns", [])
        if not isinstance(rules, list):
            raise PcbAiError("invalid_document", "Project net class patterns are not a list")
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern or len(pattern) > 256:
                raise PcbAiError("invalid_arguments", "Net patterns must be 1–256 characters")
            rules[:] = [r for r in rules if r.get("pattern") != pattern]
            rules.append(dict(netclass=name, pattern=pattern))
            assigned.append(pattern)
    changed = _dump(project, newline)
    return dict(data=changed, created=created, old=old, new={k: entry.get(v) for k, v in FIELDS.items()},
                patterns=assigned)
