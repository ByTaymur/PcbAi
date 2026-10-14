"""Separate pcb-dfm process; explicit check coverage and native calibration outrank its score."""
import json
import math
import os
import tempfile
import zipfile
from importlib.resources import files
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_program, find_kicad_cli, private_kicad_config
from pcbai.fab.profile import load as load_profile
from pcbai.fab.drill import parse as parse_drill
from pcbai.kicad.cli import snapshot
from pcbai.kicad.exports import export_fab
from pcbai.kicad.files import digest, within
from pcbai.pcb.engines.base import run_process
from pcbai.verify.findings import normalize_findings
from pcbai.verify.manifest import entry, verification
from pcbai.verify.severities import _pairs

RULES = json.loads(files("pcbai.fab").joinpath("dfm_checks.json").read_text(encoding="utf-8"))


def finite(value):
    return type(value) in {int, float} and -100000 <= value <= 100000 and math.isfinite(value)


def read_report(path):
    try:
        if not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("Missing or oversized external report")
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs,
                          parse_constant=lambda value: _invalid(value))
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise PcbAiError("invalid_dfm_report", "External pcb-dfm report could not be certified") from exc


def _invalid(value):
    raise ValueError("Nonfinite JSON number: " + value)


def canonical_view(package, destination, manifest):
    """Rename an index-only copy for a filename-based parser; artwork bytes never change."""
    mapping = []
    seen = set()
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as target:
        names = source.namelist()
        if len(names) != len(set(names)) or any(Path(name).name != name or "\\" in name for name in names):
            raise PcbAiError("invalid_package", "Unsafe or duplicate native fabrication member")
        if sum(info.file_size for info in source.infolist()) > 128 * 1024 * 1024:
            raise PcbAiError("invalid_package", "Native fabrication package exceeds size budget")
        if set(source.namelist()) != {record["name"] for record in manifest["files"]} | {"manifest.json"}:
            raise PcbAiError("invalid_package", "Fabrication package inventory differs from manifest")
        for record in manifest["files"]:
            name, role = record["name"], record["role"]
            raw = source.read(name)
            if digest(raw) != record["sha256"]:
                raise PcbAiError("invalid_package", "Fabrication bytes differ from native manifest")
            if role == "gerber":
                canonical = "pcbai-" + record["layer"].replace(".", "_") + ".gbr"
            elif role == "drill":
                # Generated native file names distinguish plated/unplated drill files.
                # Preserve that native name; do not infer plating from hole geometry.
                canonical = name
            else:
                # Rich sidecars could activate checks without independent registration.
                # The native IPC/POS/stats remain in the original package and evidence.
                continue
            if Path(canonical).name != canonical or canonical in seen:
                raise PcbAiError("invalid_package", "Unsafe or duplicate fabrication view filename")
            seen.add(canonical)
            target.writestr(canonical, raw)
            mapping.append(dict(original=name, view=canonical, sha256=digest(raw), role=role))
    return mapping


def normalize(report, profile):
    if not isinstance(report, dict) or report.get("schema_version") != "1.0.0":
        raise PcbAiError("invalid_dfm_report", "Unsupported pcb-dfm report schema")
    if any(not isinstance(report.get(key), dict) for key in ("ruleset", "summary", "run")):
        raise PcbAiError("invalid_dfm_report", "Missing pcb-dfm identity or summary")
    if report["run"].get("tool") != "pcb-dfm":
        raise PcbAiError("invalid_dfm_report", "External report tool identity is not pcb-dfm")
    if report.get("ruleset", {}).get("name") != profile["dfm_ruleset_id"]:
        raise PcbAiError("invalid_dfm_report", "pcb-dfm ruleset identity differs from requested profile")
    if report.get("summary", {}).get("geometry_source") != "gerber":
        raise PcbAiError("invalid_dfm_report", "pcb-dfm did not inspect the supplied artwork")
    required = set(profile["dfm_required_checks"])
    categories = report.get("categories")
    if not isinstance(categories, list):
        raise PcbAiError("invalid_dfm_report", "pcb-dfm check coverage is absent")
    findings, checks, seen = [], [], set()
    for category in categories:
        rows = category.get("checks") if isinstance(category, dict) else None
        if not isinstance(rows, list):
            raise PcbAiError("invalid_dfm_report", "pcb-dfm category check list is absent")
        for row in rows:
            identifier = row.get("check_id") if isinstance(row, dict) else None
            if not isinstance(identifier, str) or identifier not in RULES["checks"] or identifier in seen:
                raise PcbAiError("invalid_dfm_report", "Missing, unknown or repeated pcb-dfm check identity")
            seen.add(identifier)
            if row.get("category_id") != RULES["checks"][identifier] or category.get("category_id") != row["category_id"]:
                raise PcbAiError("invalid_dfm_report", "pcb-dfm check category differs from pinned registry")
            status, violations = row.get("status"), row.get("violations")
            if status not in {"pass", "warning", "fail", "not_applicable"} or not isinstance(violations, list):
                raise PcbAiError("invalid_dfm_report", "Unknown check status or missing violations list")
            crashed = False
            declared_confidence = row.get("confidence") or "heuristic"
            if declared_confidence not in {"heuristic", "deterministic", "high"}:
                raise PcbAiError("invalid_dfm_report", "Unknown external confidence")
            confidence = "deterministic" if declared_confidence == "deterministic" else "heuristic"
            for violation in violations:
                if not isinstance(violation, dict) or not isinstance(violation.get("message"), str):
                    raise PcbAiError("invalid_dfm_report", "Invalid external violation")
                message, severity = violation["message"], violation.get("severity")
                if severity not in {"info", "warning", "error", "critical"}:
                    raise PcbAiError("invalid_dfm_report", "Unknown external violation severity")
                if status == "pass" and severity in {"error", "critical"}:
                    raise PcbAiError("invalid_dfm_report", "Passed check contains an error violation")
                crashed |= message.startswith("Check crashed: ")
                location = violation.get("location") or {}
                if not isinstance(location, dict):
                    raise PcbAiError("invalid_dfm_report", "Invalid external violation location")
                item = {}
                x, y = location.get("x_mm"), location.get("y_mm")
                if x is not None or y is not None:
                    if not finite(x) or not finite(y):
                        raise PcbAiError("invalid_dfm_report", "External position is not a finite mm pair")
                    item["pos"] = dict(x=x, y=y)
                reference = location.get("component")
                if reference is not None:
                    if not isinstance(reference, str):
                        raise PcbAiError("invalid_dfm_report", "External component reference is not text")
                    item["reference"] = reference
                findings.append(dict(type=identifier, severity="error" if severity == "critical" else severity,
                                     description=message, items=[item] if item else [], confidence=confidence,
                                     evidence_source="geometry", external_status=status, layer=location.get("layer")))
                findings[-1]["external_confidence"] = declared_confidence
            if status in {"warning", "fail"} and not violations:
                findings.append(dict(type=identifier, severity="error" if status == "fail" else "warning",
                                     description="External check reported " + status + " without violation details",
                                     items=[], confidence="heuristic", evidence_source="geometry"))
            metric = row.get("metric")
            unmeasured = identifier in required and (not isinstance(metric, dict)
                         or not finite(metric.get("measured_value")))
            checks.append(entry("dfm:" + identifier, required=identifier in required,
                                status="failed" if crashed else "not_applicable" if status == "not_applicable" else "skipped" if unmeasured else "ran",
                                reason="external_check_crashed" if crashed else "external_not_applicable" if status == "not_applicable" else "required_geometry_unmeasured" if unmeasured else None,
                                limit_id="L-EXTERNAL-MODEL-CALIBRATION" if unmeasured and not crashed else None,
                                tool="pcb-dfm", tool_version=report.get("run", {}).get("tool_version")))
    for identifier in sorted(required - seen):
        checks.append(entry("dfm:" + identifier, status="failed", reason="missing_required_check", tool="pcb-dfm"))
    return normalize_findings(findings, "fab"), checks


def calibrate(calibration, manifest, native_stats, expected_drills=None, expected_slots=None):
    if calibration is not None and (not isinstance(calibration, dict) or type(calibration.get("schema_version")) is not int
                                    or calibration["schema_version"] != 1 or calibration.get("geometry_source") != "gerber"):
        raise PcbAiError("invalid_dfm_report", "Unknown external calibration schema or authority")
    findings, checks = [], []
    def compare(identifier, expected, observed, equal, missing=False):
        checks.append(entry("dfm_calibration:" + identifier, status="skipped" if missing else "ran",
                            reason="external_calibration_unavailable" if missing else None,
                            limit_id="L-EXTERNAL-MODEL-CALIBRATION" if missing else None, tool="calibrate"))
        if not missing and not equal:
            findings.append(dict(type="dfm_" + identifier + "_mismatch", severity="error", items=[],
                                 description="Native fabrication authority and external parser differ",
                                 expected=expected, observed=observed, confidence="deterministic"))
    expected_files = {"pcbai-"+row["layer"].replace(".", "_")+".gbr" for row in manifest["files"]
                      if row.get("layer", "").endswith(".Cu")}
    actual_files = calibration.get("copper_files") if isinstance(calibration, dict) else None
    valid_files = isinstance(actual_files, list) and all(isinstance(name, str) for name in actual_files)
    compare("copper_layers", sorted(expected_files), actual_files, valid_files and set(actual_files)==expected_files
            and len(actual_files)==len(expected_files), missing=not valid_files)
    expected_masks = {"pcbai-F_Mask.gbr", "pcbai-B_Mask.gbr"}
    native_masks = {"pcbai-"+row["layer"].replace(".", "_")+".gbr" for row in manifest["files"]
                    if row.get("layer", "").endswith(".Mask")}
    actual_masks = calibration.get("mask_files") if isinstance(calibration, dict) else None
    valid_masks = isinstance(actual_masks, list) and all(isinstance(name, str) for name in actual_masks)
    compare("mask_layers", sorted(expected_masks), actual_masks,
            valid_masks and set(actual_masks)==expected_masks and len(actual_masks)==len(expected_masks),
            missing=not valid_masks or native_masks != expected_masks)
    bounds = calibration.get("outline_bounds") if isinstance(calibration, dict) else None
    bounds_certified = isinstance(calibration, dict) and calibration.get("outline_bounds_kind") == "linear_centreline"
    for axis in ("width", "height"):
        expected = float(native_stats["board"][axis][:-3])
        value = bounds.get(axis+"_mm") if isinstance(bounds, dict) else None
        compare("board_"+axis, expected, value, finite(value) and abs(expected-value) <= .001,
                missing=not bounds_certified or not finite(value))
    observed = calibration.get("drill_hits") if isinstance(calibration, dict) else None
    compare("drill_hits", expected_drills, observed, expected_drills==observed,
            missing=type(expected_drills) is not int or type(observed) is not int or observed < 0)
    observed = calibration.get("drill_slots") if isinstance(calibration, dict) else None
    compare("drill_slots", expected_slots, observed, expected_slots==observed,
            missing=type(expected_slots) is not int or type(observed) is not int or observed < 0)
    return normalize_findings(findings, "calibration"), checks


def check(root, document, expected_revision, identity="generic", *, timeout=300):
    profile = load_profile(identity)
    use_python = bool(os.environ.get("PCBAI_PCB_DFM_PYTHON"))
    program = find_program("python", "PCBAI_PCB_DFM_PYTHON") if use_python else find_program("pcb-dfm", "PCBAI_PCB_DFM")
    with snapshot(root, expected_revision) as copy, tempfile.TemporaryDirectory(prefix="pcbai-dfm-") as temporary:
        source = within(copy, document)
        if source.suffix != ".kicad_pcb":
            raise PcbAiError("invalid_document", "DFM requires a PCB")
        from pcbai.kicad.board import summary
        allowed = profile["scope"].get("copper_layers")
        if allowed and summary(source.read_bytes())["copper_layer_count"] not in allowed:
            raise PcbAiError("profile_scope_mismatch", "PCB layer count does not match DFM profile")
        work = Path(temporary)
        # Bare-board DFM is independent of assembly readiness/paste-side policy.
        manifest = export_fab(copy, document, work/"native.zip", expected_revision, assembly=False)
        mapping = canonical_view(work/"native.zip", work/"view.zip", manifest)
        native_hash = digest((work/"native.zip").read_bytes())
        view_hash = digest((work/"view.zip").read_bytes())
        with zipfile.ZipFile(work/"native.zip") as archive:
            native_stats = json.loads(archive.read("board-stats.json"))
            expected_drills, expected_slots = 0, 0
            try:
                for record in manifest["files"]:
                    if record["role"] == "drill":
                        parsed = parse_drill(archive.read(record["name"]))
                        expected_drills += len(parsed["hits"])
                        expected_slots += len(parsed["slots"])
            except PcbAiError:
                expected_drills, expected_slots = None, None
        env = dict(os.environ, KICAD_CONFIG_HOME=str(private_kicad_config(find_kicad_cli(), work/"config")),
                   PYTHONSAFEPATH="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        report_path, calibration_path = work/"report.json", work/"calibration.json"
        if use_python:
            request = dict(package=str(work/"view.zip"), ruleset=profile["dfm_ruleset_id"],
                           report=str(report_path), calibration=str(calibration_path))
            (work/"request.json").write_text(json.dumps(request), encoding="utf-8")
            argv = [program, "-I", "-X", "utf8", Path(__file__).with_name("dfm_worker.py"), work/"request.json"]
        else:
            argv = [program, "run", work/"view.zip", "--ruleset", profile["dfm_ruleset_id"],
                    "--format", "json", "--output", report_path]
        process = run_process(argv, cwd=work, timeout=timeout, env=env)
        if process["returncode"]:
            raise PcbAiError("dfm_failed", "Separate pcb-dfm process failed", details=process)
        if digest((work/"native.zip").read_bytes()) != native_hash or digest((work/"view.zip").read_bytes()) != view_hash:
            raise PcbAiError("external_mutated_input", "External program altered immutable fabrication input")
        report = read_report(report_path)
        findings, checks = normalize(report, profile)
        calibration = read_report(calibration_path) if calibration_path.is_file() else None
        if calibration is not None and calibration.get("package_sha256") != view_hash:
            raise PcbAiError("invalid_dfm_report", "External calibration belongs to different fabrication bytes")
        calibration_findings, calibration_checks = calibrate(calibration, manifest, native_stats, expected_drills, expected_slots)
        findings.extend(calibration_findings)
        checks.extend(calibration_checks)
        hashes = dict(native_package=native_hash, view_package=view_hash,
                      report=digest(report_path.read_bytes()), profile=profile["sha256"])
        for row in checks:
            row.update(inputs_sha256=hashes, seconds=process["seconds"])
        return dict(verified=verification(checks, findings), findings=findings, checks_run=checks, profile=profile,
                    report=report, calibration=calibration, inputs_sha256=hashes, filename_view=mapping,
                    production_verified=False, original_revision=expected_revision, elapsed_seconds=process["seconds"],
                    threshold_authority="external_pcb_dfm_ruleset", native_fab_profile_checked=False,
                    external_program=dict(path=program, sha256=digest(Path(program).read_bytes()),
                                          version_verified=False), stock_and_assembly_verified=False)
