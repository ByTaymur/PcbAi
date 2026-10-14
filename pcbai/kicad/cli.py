import json
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli, run
from pcbai.kicad.dru import preflight, probe_rules
from pcbai.kicad.files import digest, project_files, project_bytes, revision, within, WAIVER_FILE
from pcbai.sexpr import Document
from pcbai.verify.findings import normalize_findings
from pcbai.verify.severities import ignored_rules


@contextmanager
def snapshot(root, expected_revision=None):
    """Copy all project inputs, retaining sheet-relative paths and local libraries."""
    root = Path(root).resolve()
    with tempfile.TemporaryDirectory(prefix="pcbai-check-") as temporary:
        target = Path(temporary)
        for source in project_files(root):
            dest = target / source.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source.name == WAIVER_FILE:
                dest.write_bytes(project_bytes(source))
            else:
                shutil.copyfile(source, dest)
        if expected_revision is not None and revision(target) != expected_revision:
            raise PcbAiError("stale_revision", "Project changed while creating the snapshot; inspect again")
        # Reject external hierarchical sheets: avoid reading files outside registered roots.
        for sheet in target.rglob("*.kicad_sch"):
            doc = Document(sheet.read_bytes())
            for node in doc.root.all("sheet"):
                for prop in node.all("property"):
                    if prop.value() in {"Sheetfile", "Sheet file"}:
                        name = prop.value(2).replace("${KIPRJMOD}", str(target))
                        within(target, str(sheet.parent / name))
        yield target


def rule_check(root, document, kind, *, parity=False, override=None, expected_revision=None,
               override_document=None):
    """Check ``document``; ``override`` replaces ``override_document`` (default: the checked file)."""
    if kind not in {"erc", "drc"}:
        raise PcbAiError("invalid_arguments", "Unknown check kind")
    cli = find_kicad_cli()
    with snapshot(root, expected_revision) as copy:
        source = within(copy, document)
        if override is not None:
            within(copy, override_document or document).write_bytes(override)
        inputs = {p.relative_to(copy).as_posix(): digest(project_bytes(p)) for p in project_files(copy)}
        custom = custom_rules_gate(cli, copy, source) if kind == "drc" else None
        report_file = copy / "pcbai-check.json"
        argv = [cli, "sch" if kind == "erc" else "pcb", kind, str(source), "--format", "json",
                "--output", str(report_file), "--units", "mm", "--severity-all", "--exit-code-violations"]
        if kind == "drc" and parity:
            argv.append("--schematic-parity")
        process = run(argv, cwd=copy)
        if custom and custom["rules"] and process.returncode == 3:
            # KiCad builds that fail DRC on rules which do not compile (master, not 10.0.x) exit 3.
            raise PcbAiError("custom_rules_invalid", "KiCad could not compile the custom DRC rules: "
                             + (process.stderr or process.stdout)[-2000:])
        if process.returncode not in {0, 5} or not report_file.is_file():
            raise PcbAiError("check_failed", f"KiCad {kind.upper()} failed (exit {process.returncode}): "
                             + (process.stderr or process.stdout)[-2000:])
        try:
            report = json.loads(report_file.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise PcbAiError("invalid_report", "KiCad did not produce a valid JSON report") from exc
        findings = []
        if kind == "erc":
            if not isinstance(report.get("sheets"), list) or not report["sheets"]:
                raise PcbAiError("invalid_report", "ERC report has no sheets list")
            for sheet in report["sheets"]:
                violations = sheet.get("violations")
                if not isinstance(violations, list):
                    raise PcbAiError("invalid_report", "ERC sheet has no violations list")
                findings.extend(dict(item, sheet=sheet.get("path")) for item in violations)
        else:
            for group in ("violations", "unconnected_items", "schematic_parity"):
                if not isinstance(report.get(group), list):
                    raise PcbAiError("invalid_report", f"DRC report missing {group}")
                findings.extend(dict(item, group=group) for item in report[group])
        errors = sum(f.get("severity") == "error" and not f.get("excluded", False) for f in findings)
        warnings = sum(f.get("severity") == "warning" and not f.get("excluded", False) for f in findings)
        excluded = sum(f.get("excluded", False) or f.get("severity") in {"exclusion", "ignore"} for f in findings)
        unknown = [f for f in findings if f.get("severity") not in {"error", "warning", "exclusion", "ignore"}]
        if unknown:
            raise PcbAiError("invalid_report", "Unknown finding severity; check cannot be certified")
        if process.returncode == 5 and not findings:
            raise PcbAiError("invalid_report", "KiCad reported violations but its report contains no findings")
        ignored = ignored_rules(copy, document, kind, report, parity=parity)
        return dict(errors=errors, warning_count=warnings, excluded_count=excluded,
                    findings=normalize_findings(findings, kind), report=report, custom_rules=custom,
                    ignored_rules=ignored, inputs_sha256=inputs, exit_code=process.returncode,
                    clean=errors == 0 and warnings == 0 and excluded == 0 and not any(r["required"] for r in ignored))


_PROBES = {}


def custom_rules_gate(cli, copy, board):
    """Fail closed when the board's .kicad_dru is malformed or KiCad did not load it (see pcbai.kicad.dru).

    Returns {status, rules, sha256, probe}; status is not_applicable (no rules), loaded or unverified
    (probe found no copper to fire on). Raises custom_rules_invalid / custom_rules_not_loaded.
    """
    rules_file = board.with_suffix(".kicad_dru")
    if not rules_file.is_file():
        return dict(status="not_applicable", rules=0, sha256=None, probe=None)
    data = rules_file.read_bytes()
    checked = preflight(data)
    if checked["problems"]:
        raise PcbAiError("custom_rules_invalid", "Custom DRC rules are malformed; KiCad 10 would drop them "
                         "silently: " + "; ".join(checked["problems"][:10]), details=checked)
    if not checked["rules"]:
        return dict(status="not_applicable", rules=0, sha256=digest(data), probe=None)
    key = (str(cli), digest(board.read_bytes()), digest(data))
    if key not in _PROBES:
        name, probed = probe_rules(data)
        output = copy / "pcbai-rules-probe.json"
        try:
            rules_file.write_bytes(probed)
            process = run([cli, "pcb", "drc", str(board), "--format", "json", "--output", str(output),
                           "--units", "mm", "--severity-all"], cwd=copy)
        finally:
            rules_file.write_bytes(data)
        if process.returncode == 3:
            raise PcbAiError("custom_rules_invalid", "KiCad could not compile the custom DRC rules: "
                             + (process.stderr or process.stdout)[-2000:])
        if process.returncode not in {0, 5} or not output.is_file():
            raise PcbAiError("check_failed", f"Custom rule probe DRC failed (exit {process.returncode})")
        text = output.read_text(encoding="utf-8")
        try:
            fired = json.loads(text).get("violations") or []
        except ValueError as exc:
            raise PcbAiError("invalid_report", "Custom rule probe produced no valid JSON report") from exc
        status = "loaded" if name in text else ("unverified" if not fired else "not_loaded")
        if len(_PROBES) > 32:
            _PROBES.clear()
        _PROBES[key] = status
    status = _PROBES[key]
    if status == "not_loaded":
        raise PcbAiError("custom_rules_not_loaded", "KiCad ignored the custom DRC rules file (a probe rule "
                         "appended to it never fired); fix the rules before trusting DRC", details=checked)
    return dict(status=status, rules=checked["rules"], sha256=digest(data), probe="probe_rule_fired"
                if status == "loaded" else "no_copper_for_probe")


def export_pdf(root, document, destination, expected_revision=None):
    cli = find_kicad_cli()
    with snapshot(root, expected_revision) as copy:
        source = within(copy, document)
        process = run([cli, "sch", "export", "pdf", str(source), "--output", str(destination)], cwd=copy)
        if process.returncode or not Path(destination).is_file():
            raise PcbAiError("export_failed", (process.stderr or process.stdout)[-2000:])


def refill(root, document, data, expected_revision=None):
    """Let KiCad fill zones of ``data`` in an isolated copy and return the board KiCad saved."""
    cli = find_kicad_cli()
    with snapshot(root, expected_revision) as copy:
        source = within(copy, document)
        source.write_bytes(data)
        report = copy / "pcbai-refill.json"
        process = run([cli, "pcb", "drc", str(source), "--format", "json", "--output", str(report),
                       "--units", "mm", "--refill-zones", "--save-board"], cwd=copy)
        if process.returncode not in {0, 5}:
            raise PcbAiError("check_failed", "KiCad zone fill failed: " + (process.stderr or process.stdout)[-2000:])
        return source.read_bytes()
