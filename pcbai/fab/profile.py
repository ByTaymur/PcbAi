"""Apply bounded manufacturing minima to a disposable project only."""
import json
import math
from importlib.resources import files

from pcbai.core.contract import PcbAiError
from pcbai.kicad.cli import snapshot, rule_check
from pcbai.kicad.files import digest, revision, within
from pcbai.verify.findings import normalize_findings
from pcbai.verify.severities import _pairs, MAX_SETTINGS_BYTES

IDS = ("generic", "jlcpcb-2l", "jlcpcb-4l", "pcbway", "oshpark")
KEYS = frozenset({"min_clearance", "min_track_width", "min_through_hole_diameter",
                  "min_via_annular_width", "min_copper_edge_clearance", "min_text_height",
                  "min_text_thickness", "min_silk_clearance"})


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 25 or not math.isfinite(value):
        raise PcbAiError("invalid_profile", "Manufacturing minima must be finite millimetres between 0 and 25")
    return value


def load(identity):
    if identity not in IDS:
        raise PcbAiError("invalid_profile", "Unknown bundled fabrication profile")
    raw = files("pcbai.fab.profiles").joinpath(identity + ".json").read_bytes()
    profile = json.loads(raw)
    if profile["id"] != identity or profile["qualifier"] != "üreticiyle doğrulayın":
        raise PcbAiError("invalid_profile", "Profile identity or verification qualifier missing")
    for key, record in profile["minimums"].items():
        if key not in KEYS or not record.get("source_url") or not record.get("retrieved"):
            raise PcbAiError("invalid_profile", "Unattributed or unknown manufacturing minimum")
        number(record["value_mm"])
    return dict(profile, sha256=digest(raw))


def describe():
    return [load(identity) for identity in IDS]


def read_settings(path):
    try:
        if path.stat().st_size > MAX_SETTINGS_BYTES:
            raise ValueError("Project settings too large")
        value = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs,
                           parse_constant=lambda item: number(float(item)))
        for key in ("board", "design_settings", "rules", "rule_severities"):
            container = value if key == "board" else value["board"] if key == "design_settings" else value["board"]["design_settings"]
            if not isinstance(container, dict):
                raise ValueError("Settings container is not an object")
            container.setdefault(key, {})
            if not isinstance(container[key], dict):
                raise ValueError("Settings container is not an object")
        rules = value["board"]["design_settings"]["rules"]
        for key in KEYS & rules.keys():
            number(rules[key])
        return value
    except (OSError, ValueError, TypeError, RecursionError, UnicodeError) as exc:
        raise PcbAiError("invalid_project_settings", "Cannot certify fabrication profile settings") from exc


def tighten(settings, profile, baseline, overrides=None):
    """Never infer a missing saved minimum as zero; baseline must be measured."""
    overrides = {} if overrides is None else overrides
    if not isinstance(overrides, dict) or set(overrides) - KEYS:
        raise PcbAiError("invalid_profile", "Unknown manufacturing override")
    rules = settings["board"]["design_settings"]["rules"]
    effective = {}
    for key in sorted(set(profile["minimums"]) | set(overrides)):
        saved = rules.get(key, baseline.get(key))
        if saved is None:
            raise PcbAiError("profile_defaults_unavailable", "Native default unavailable for " + key)
        saved = max(number(saved), number(baseline[key])) if key in baseline else number(saved)
        requested = number(profile["minimums"].get(key, {}).get("value_mm", saved))
        floor = max(saved, requested)
        if key in overrides:
            requested = number(overrides[key])
            if requested < floor:
                raise PcbAiError("profile_loosening", "Requested minimum would loosen " + key)
            floor = requested
        rules[key] = floor
        effective[key] = dict(before_mm=saved, profile_mm=profile["minimums"].get(key, {}).get("value_mm"),
                              effective_mm=floor, baseline="saved" if key in baseline.get("saved_keys", []) else "native_default")
    return effective


def check(root, document, expected_revision, identity, *, overrides=None, baseline_reader=None):
    with snapshot(root, expected_revision) as copy:
        return check_copy(copy, document, expected_revision, identity, overrides=overrides, baseline_reader=baseline_reader)


def check_copy(copy, document, expected_revision, identity, *, overrides=None, baseline_reader=None):
    """Mutate only a caller-owned disposable snapshot; retain it for identical export inputs."""
    if revision(copy) != expected_revision:
        raise PcbAiError("stale_revision", "Fabrication candidate changed before profile check")
    profile = load(identity)
    board = within(copy, document)
    if board.suffix != ".kicad_pcb":
        raise PcbAiError("invalid_document", "Fabrication profiles require a PCB")
    from pcbai.kicad.board import summary
    count = summary(board.read_bytes())["copper_layer_count"]
    allowed = profile["scope"].get("copper_layers")
    if allowed and count not in allowed:
        raise PcbAiError("profile_scope_mismatch", "PCB layer count does not match profile")
    project = within(copy, str(board.relative_to(copy).with_suffix(".kicad_pro")))
    settings = read_settings(project)
    original_rules = settings["board"]["design_settings"]["rules"]
    if profile["minimums"] or overrides:
        if baseline_reader is None:
            from pcbai.fab.settings import native_defaults
            baseline_reader = native_defaults
        baseline = dict(baseline_reader(copy, document), saved_keys=list(original_rules))
        effective = tighten(settings, profile, baseline, overrides)
    else:
        effective = {}
    # Discover native ignored IDs first, then promote those IDs only in the copy.
    before = rule_check(copy, document, "drc", expected_revision=revision(copy))
    severities = settings["board"]["design_settings"]["rule_severities"]
    # An unknown project severity ID is not proof of a supported native rule.
    # Leave it suppressed and incomplete instead of certifying a blind promotion.
    promoted = sorted({item["rule"] for item in before["ignored_rules"] if "native" in item["sources"]})
    for rule in promoted:
        severities[rule] = "error"
    project.write_text(json.dumps(settings, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    output = rule_check(copy, document, "drc", expected_revision=revision(copy))
    output["findings"] = normalize_findings(output["findings"], "fab_profile")
    return dict(output, profile=profile, effective_minimums=effective, promoted_rules=promoted,
                original_revision=expected_revision, checked_revision=revision(copy),
                production_verified=False, assembly_format_verified=False)
