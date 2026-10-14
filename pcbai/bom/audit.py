"""Native component metadata audit; no invented part identity or assembly verdict."""

import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pcbai.bom.values import canonical, rating
from pcbai.core.contract import PcbAiError
from pcbai.fab.profile import load
from pcbai.kicad.cli import snapshot
from pcbai.kicad.files import digest, within
from pcbai.sch_render import export_netlist
from pcbai.verify.findings import normalize_findings
from pcbai.verify.manifest import entry, verification

ALIASES = {
    "footprint": {"footprint"},
    "mpn": {"mpn", "manufacturer part number", "manufacturer_part_number"},
    "manufacturer": {"manufacturer", "mfr"},
    "lcsc": {"lcsc", "lcsc part", "lcsc_part", "lcsc part number"},
    "tolerance": {"tolerance", "tol"},
    "voltage": {"voltage", "voltage rating", "voltage_rating"},
    "dielectric": {"dielectric"},
}


def components(data):
    if len(data) > 16 * 1024 * 1024 or b"<!ENTITY" in data.upper() or b"<!DOCTYPE" in data.upper():
        raise PcbAiError("invalid_bom", "Native metadata exceeds limits or declares XML entities")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise PcbAiError("invalid_bom", "Native component metadata is invalid XML") from exc
    containers = root.findall("components")
    if root.tag != "export" or len(containers) != 1:
        raise PcbAiError("invalid_bom", "Native component container is absent or ambiguous")
    nodes = containers[0].findall("comp")
    if not 0 < len(nodes) <= 10000:
        raise PcbAiError("invalid_bom", "Native component count is empty or exceeds limits")
    rows, refs = [], set()
    for node in nodes:
        ref = node.get("ref")
        if not ref or len(ref) > 128 or ref.casefold() in refs:
            raise PcbAiError("invalid_bom", "Native references are absent or duplicated")
        refs.add(ref.casefold())
        fields, names = {}, set()
        raw_fields = node.findall("fields/field")
        if len(raw_fields) > 128:
            raise PcbAiError("invalid_bom", "Too many component fields")
        for field in raw_fields:
            name, value = field.get("name"), field.text or ""
            if not name or len(name) > 128 or len(value) > 4096 or name.casefold() in names:
                raise PcbAiError("invalid_bom", "Ambiguous or oversized native field")
            names.add(name.casefold())
            fields[name] = value
        for tag in ("value", "footprint", "libsource", "sheetpath"):
            if len(node.findall(tag)) > 1:
                raise PcbAiError("invalid_bom", "Repeated native component identity field")
        footprint = node.findtext("footprint") or ""
        if len(footprint) > 4096 or any(
            name.casefold() == "footprint" and value.strip() and value.strip() != footprint.strip()
            for name, value in fields.items()
        ):
            raise PcbAiError("invalid_bom", "Native footprint field conflicts with footprint identity")
        value = node.findtext("value") or ""
        if len(value) > 4096:
            raise PcbAiError("invalid_bom", "Oversized native component value")
        lib = node.find("libsource")
        part = lib.get("part", "") if lib is not None else ""
        library = lib.get("lib", "") if lib is not None else ""
        sheet = node.find("sheetpath")
        rows.append(
            dict(
                reference=ref,
                value=value,
                fields=fields,
                native_footprint=footprint.strip(),
                library=library,
                part=part,
                sheet=sheet.get("tstamps") if sheet is not None else None,
            )
        )
    return rows


def category(row):
    lib, part = row["library"], row["part"]
    if lib == "Device":
        if part in {"R", "R_Small", "R_US", "R_Small_US"}:
            return "resistor"
        if part in {"C", "C_Small", "C_Polarized", "C_Polarized_Small"}:
            return "capacitor"
        if part.startswith(("D", "LED", "Q_", "L", "Crystal", "Ferrite")):
            return "other"
    if lib.startswith(
        (
            "Connector",
            "MCU_",
            "Regulator_",
            "Amplifier_",
            "Interface_",
            "Logic_",
            "Transistor_",
            "Diode",
            "Switch",
        )
    ):
        return "other"
    return None


def audit(data, identity="generic"):
    profile = load(identity)
    rows = components(data)
    findings, checks, groups = [], [], {}

    def finding(rule, row, description, severity="warning", **extra):
        findings.append(
            dict(
                type=rule,
                severity=severity,
                description=description,
                group=row["reference"] + ":" + extra.get("field", ""),
                items=[dict(reference=row["reference"], sheet=row["sheet"])]
                if row["sheet"]
                else [dict(reference=row["reference"])],
                confidence="deterministic",
                **extra,
            )
        )

    required_fields = ["footprint", "mpn", "manufacturer"] + (
        ["lcsc"] if identity.startswith("jlcpcb-") else []
    )
    missing_count = 0
    for row in rows:
        selected, conflicts = {}, set()
        for key, aliases in ALIASES.items():
            matches = [
                (name, value.strip()) for name, value in row["fields"].items() if name.casefold() in aliases
            ]
            nonempty = {value for _, value in matches if value}
            if len(nonempty) > 1:
                conflicts.add(key)
                finding(
                    "bom_field_alias_conflict",
                    row,
                    "Component field aliases contain different literal identities",
                    severity="error",
                    field=key,
                    values=sorted(nonempty),
                )
            selected[key] = next(iter(nonempty)) if len(nonempty) == 1 else ""
        selected["footprint"] = row["native_footprint"]
        row["selected_fields"] = selected
        cat = category(row)
        row["category"] = cat
        required = required_fields + (
            ["tolerance"] if cat == "resistor" else ["voltage", "dielectric"] if cat == "capacitor" else []
        )
        for field in required:
            if not selected[field] and field not in conflicts:
                missing_count += 1
                finding(
                    "bom_missing_field",
                    row,
                    "Required component field is absent",
                    field=field,
                    severity="error",
                    suggestion="Supply a verified " + field + "; no value is assigned automatically",
                )
        checks.append(entry("bom:fields:" + row["reference"], tool="native_component_fields"))
        if not row["value"].strip():
            missing_count += 1
            finding("bom_missing_field", row, "Component Value is absent", field="value", severity="error")
        checks.append(
            entry(
                "bom:category:" + row["reference"],
                status="ran" if cat is not None else "skipped",
                reason=None if cat is not None else "unsupported_library_category",
                tool="native_library_identity",
            )
        )
        normalized = (
            canonical(cat, row["value"]) if cat in {"resistor", "capacitor"} else row["value"].strip()
        )
        row["canonical_value"] = normalized
        if cat in {"resistor", "capacitor"}:
            checks.append(
                entry(
                    "bom:value:" + row["reference"],
                    status="ran" if normalized is not None else "skipped",
                    reason=None if normalized is not None else "ambiguous_passive_notation",
                    tool="bounded_decimal",
                )
            )
            if normalized is None:
                finding(
                    "bom_ambiguous_value", row, "Passive value notation has no supported exact interpretation"
                )
            for field in ("tolerance", "voltage"):
                if selected[field] and rating(selected[field], field) is None:
                    finding(
                        "bom_invalid_rating",
                        row,
                        "Rating has no supported explicit unit or range",
                        field=field,
                    )
            prefix = "Capacitor_" if cat == "resistor" else "Resistor_"
            if selected["footprint"].startswith(prefix):
                finding(
                    "bom_footprint_category_conflict",
                    row,
                    "Native symbol category conflicts with declared footprint family",
                    severity="error",
                )
        if normalized is not None:
            key = (cat, normalized, selected["footprint"])
            groups.setdefault(key, []).append(row)
    output_groups = []
    for (cat, value, footprint), members in groups.items():
        raw_values = sorted({row["value"] for row in members})
        if len(raw_values) > 1 and cat in {"resistor", "capacitor"}:
            finding(
                "bom_value_format_variation",
                members[0],
                "Equivalent passive values use different text spellings",
                references=[row["reference"] for row in members],
                raw_values=raw_values,
                suggested_canonical_si=value,
            )
        for field in ("mpn", "manufacturer", "lcsc", "tolerance", "voltage", "dielectric"):
            values = sorted({row["selected_fields"][field] for row in members})
            if len(values) > 1:
                finding(
                    "bom_group_field_variation",
                    members[0],
                    "Same value/footprint group has different metadata; separate purchasing groups may be intentional",
                    field=field,
                    values=values,
                    references=[row["reference"] for row in members],
                )
        output_groups.append(
            dict(
                category=cat,
                canonical_value=value,
                footprint=footprint,
                references=[row["reference"] for row in members],
                quantity=len(members),
            )
        )
    findings = normalize_findings(findings, "bom")
    for row in checks:
        row["inputs_sha256"] = dict(native_xml=digest(data), profile=profile["sha256"])
    return dict(
        findings=findings,
        checks_run=checks,
        verified=verification(checks, findings),
        components=rows,
        value_groups=output_groups,
        missing_field_count=missing_count,
        profile=identity,
        production_verified=False,
        assembly_verified=False,
        part_identity_verified=False,
        component_scope="native_netlist_export_included_components",
        excluded_component_coverage_verified=False,
    )


def check(root, document, expected_revision, identity="generic"):
    with (
        snapshot(root, expected_revision) as copy,
        tempfile.TemporaryDirectory(prefix="pcbai-bom-") as temporary,
    ):
        source = within(copy, document)
        if (
            source.suffix != ".kicad_sch"
            or source.parent != copy
            or not source.with_suffix(".kicad_pro").is_file()
        ):
            raise PcbAiError("invalid_document", "BOM field audit requires the root schematic")
        data = export_netlist(copy, document, Path(temporary) / "native.xml")
        output = audit(data, identity)
        output.update(original_revision=expected_revision, native_xml_sha256=digest(data))
        return output
