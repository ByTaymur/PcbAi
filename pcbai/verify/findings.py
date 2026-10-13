"""Normalize findings without losing native fields or report multiplicity.

Identity ignores descriptions, file paths, evidence IDs and positions of UUID-bearing
items. UUID-less positions use decimal round-to-even at 0.001 mm. Duplicate ordinals
identify report rows; comparison uses the base identity with a Counter so a 1→2
transition introduces one error rather than changing both rows' identities.
"""
import copy
import hashlib
import json
import math
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from importlib.resources import files

from jsonschema import Draft202012Validator

from pcbai.core.contract import PcbAiError


SCHEMA = json.loads(files("pcbai.verify").joinpath("finding.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA)
SOURCES = {"erc", "drc", "parity", "engine", "calibration", "readback"}
EVIDENCE_SOURCES = dict(erc="kicad", drc="kicad", parity="kicad", engine="geometry",
                        calibration="topology", readback="topology")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def coordinate(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PcbAiError("invalid_report", "Finding position must be a finite number")
    try:
        rounded = Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN)
    except InvalidOperation as exc:
        raise PcbAiError("invalid_report", "Finding position exceeds supported precision") from exc
    return "0.000" if rounded == 0 else str(rounded)


def normalize_findings(findings, source=None, *, evidence_id=None):
    """Return independent normalized rows, preserving their input order and native fields.

    An explicit source comes from the check that ran. Without it, normalized source
    is retained; legacy ERC sheet and DRC parity group metadata provide the fallback.
    """
    if not isinstance(findings, list):
        raise PcbAiError("invalid_report", "Findings must be a list")
    rows, duplicates = [], defaultdict(list)
    for raw in findings:
        if not isinstance(raw, dict):
            raise PcbAiError("invalid_report", "Finding must be an object")
        origin = source if source is not None else raw.get("source", "erc" if "sheet" in raw else "drc")
        if origin == "drc" and raw.get("group") == "schematic_parity":
            origin = "parity"
        if not isinstance(origin, str) or origin not in SOURCES:
            raise PcbAiError("invalid_report", "Unknown finding source")
        # Older consumers/tests can supply a counted finding without KiCad's optional type field.
        rule = raw.get("type", raw.get("rule_id", "unknown"))
        if not isinstance(rule, str) or not rule:
            raise PcbAiError("invalid_report", "Finding has no rule identifier")
        severity = raw.get("severity")
        excluded = raw.get("excluded", False)
        if not isinstance(excluded, bool):
            raise PcbAiError("invalid_report", "Finding excluded flag must be boolean")
        row = copy.deepcopy(raw)
        if not isinstance(severity, str):
            raise PcbAiError("invalid_report", "Unknown finding severity")
        if severity in {"exclusion", "ignore"}:
            row["raw_severity"] = severity
            original = raw.get("original_severity")
            severity = original if isinstance(original, str) and original in {"error", "warning"} else "warning"
            excluded = True
        if not isinstance(severity, str) or severity not in {"error", "warning", "info"}:
            raise PcbAiError("invalid_report", "Unknown finding severity")
        if severity == "info" and origin in {"erc", "drc", "parity"}:
            raise PcbAiError("invalid_report", "Unknown KiCad finding severity")
        items = row.get("items", [])
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise PcbAiError("invalid_report", "Finding items must be objects in a list")
        signatures = []
        for item in items:
            uid = item.get("uuid", "")
            if not isinstance(uid, str):
                raise PcbAiError("invalid_report", "Finding item UUID must be text")
            pos = item.get("pos", {})
            if not isinstance(pos, dict):
                raise PcbAiError("invalid_report", "Finding item position must be an object")
            x, y = coordinate(pos.get("x")), coordinate(pos.get("y"))
            signatures.append(["uuid", uid] if uid else ["pos", x, y])
        payload = canonical([origin, rule, raw.get("group"), sorted(signatures, key=canonical)])
        base = f"{origin}:{rule}:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        row.update(finding_id=base, source=origin, rule_id=rule, severity=severity, excluded=excluded,
                   confidence=raw.get("confidence", "deterministic") if origin == "engine" else "deterministic",
                   evidence_source=EVIDENCE_SOURCES[origin] if origin in {"erc", "drc", "parity"}
                   else raw.get("evidence_source", EVIDENCE_SOURCES[origin]), items=items)
        if "description" in raw:
            row["message"] = raw["description"]
        if items and {"x", "y"} <= set(items[0].get("pos", {})):
            row["position_mm"] = [items[0]["pos"]["x"], items[0]["pos"]["y"]]
        if evidence_id is not None:
            row["evidence_id"] = evidence_id
        failure = next(VALIDATOR.iter_errors(row), None)
        if failure:
            raise PcbAiError("invalid_report", "Finding does not match the common schema: " + failure.message)
        index = len(rows)
        rows.append(row)
        duplicates[base].append((index, (payload, severity, excluded, row.get("message", ""), canonical(items))))
    for indices in duplicates.values():
        if len(indices) > 1:
            for ordinal, (index, _) in enumerate(sorted(indices, key=lambda entry: entry[1]), 1):
                rows[index]["finding_id"] += f"#{ordinal}"
    return rows


def comparison_id(finding):
    """The base finding ID, with multiplicity tracked separately by the caller."""
    return normalize_findings([finding])[0]["finding_id"]
