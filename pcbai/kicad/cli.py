import json
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli, run
from pcbai.kicad.files import project_files, revision, within
from pcbai.sexpr import Document
from pcbai.verify.findings import normalize_findings


@contextmanager
def snapshot(root, expected_revision=None):
    """Copy all project inputs, retaining sheet-relative paths and local libraries."""
    root = Path(root).resolve()
    with tempfile.TemporaryDirectory(prefix="pcbai-check-") as temporary:
        target = Path(temporary)
        for source in project_files(root):
            dest = target / source.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
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
        report_file = copy / "pcbai-check.json"
        argv = [cli, "sch" if kind == "erc" else "pcb", kind, str(source), "--format", "json",
                "--output", str(report_file), "--units", "mm", "--severity-all", "--exit-code-violations"]
        if kind == "drc" and parity:
            argv.append("--schematic-parity")
        process = run(argv, cwd=copy)
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
        return dict(errors=errors, warning_count=warnings, excluded_count=excluded,
                    findings=normalize_findings(findings, kind), report=report,
                    exit_code=process.returncode, clean=errors == 0 and warnings == 0 and excluded == 0)


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
