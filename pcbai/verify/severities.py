"""Read saved KiCad rule suppression without changing project settings."""
import json
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.kicad.files import within

# Baseline electrical/geometric scope. Assembly/library/style diagnostics remain
# visible but optional here; a future manufacturing profile may require them.
OPTIONAL = {
    "drc": frozenset({"footprint_filters_mismatch", "footprint_type_mismatch", "missing_courtyard",
                      "track_not_centered_on_via", "tuning_profile_track_geometries"}),
    "erc": frozenset({"footprint_filter", "four_way_junction", "simulation_model_issue", "single_global_label"}),
}
MAX_SETTINGS_BYTES = 8 * 1024 * 1024


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _object(value):
    if not isinstance(value, dict):
        raise ValueError("Rule settings must be JSON objects")
    return value


def ignored_rules(root, document, kind, report, *, parity=False):
    """Union explicit settings and native ignored_checks from the same snapshot.

    Unknown ignored rule IDs are required, rather than silently treated as safe.
    """
    if kind not in OPTIONAL:
        raise PcbAiError("invalid_arguments", "Unknown rule-check kind")
    project_name = str(Path(document).with_suffix(".kicad_pro"))
    project = within(root, project_name, must_exist=False)
    suppressed = {}
    if project.is_file():
        try:
            if project.stat().st_size > MAX_SETTINGS_BYTES:
                raise ValueError("Project settings exceed the size limit")
            data = _object(json.loads(project.read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs,
                                      parse_constant=lambda value: _invalid_constant(value)))
            containers = ("board", "design_settings") if kind == "drc" else ("erc",)
            for key in containers:
                data = _object(data.get(key, {}))
            severities = _object(data.get("rule_severities", {}))
            for key, value in severities.items():
                if not isinstance(key, str) or not key or len(key) > 256 or value not in ("error", "warning", "ignore"):
                    raise ValueError("Invalid rule ID or severity")
                if value == "ignore":
                    suppressed[key] = {"project"}
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            raise PcbAiError("invalid_project_settings", "Cannot certify KiCad rule severity settings") from exc
    if "ignored_checks" not in report:
        raise PcbAiError("invalid_report", "Native report omits ignored-check coverage")
    native = report["ignored_checks"]
    if not isinstance(native, list):
        raise PcbAiError("invalid_report", "Native ignored_checks must be a list")
    for row in native:
        key = row.get("key") if isinstance(row, dict) else None
        if not isinstance(key, str) or not key or len(key) > 256:
            raise PcbAiError("invalid_report", "Invalid native ignored-check identity")
        suppressed.setdefault(key, set()).add("native")
    return [dict(rule=key, required=key not in OPTIONAL[kind] and (key != "schematic_parity" or parity),
                 sources=sorted(suppressed[key]), project_document=project_name if "project" in suppressed[key] else None)
            for key in sorted(suppressed)]


def _invalid_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")
