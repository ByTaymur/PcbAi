"""U0 local development probes. External sources stay outside the PcbAi package."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pcbai.external import find_kicad_cli, private_kicad_config, run  # noqa: E402
from pcbai.kicad.exports import export_fab  # noqa: E402
from pcbai.kicad.files import revision  # noqa: E402
from pcbai.tools.engine import Engine  # noqa: E402

PINS = {
    "jbom": "8e98cd31706c30ca42ec840f1e7a8a66a82af50a",
    "bom_cpl": "2fc86b7fc8c19d50009053ef1b4ce3c0bde3a02c",
    "dfm": "b94d0f7a39f4a743de736906f74f9973d74b989d",
    "astra": "6102d864ddaa59bf43f7e451da9edbece588d8be",
    "esim": "1a25a46ce15e0ccc35296dd513f40249c089a5a7",
    "hbee": "9ec0c21ae3fe07037e5df4f81fffaf271a7b1244",
    "inspector": "d29e1208d4cdcd07ebac7f8632c9554cbd18121b",
}
BOOTSTRAP = ("import sys,runpy; sys.path.insert(0,sys.argv.pop(1)); "
             "runpy.run_module(sys.argv.pop(1),run_name='__main__')")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(path):
    """Only permit paths in this workspace; reject linked ancestors before mkdir."""
    path = Path(os.path.abspath(path))
    path.relative_to(ROOT)
    for parent in [path, *path.parents]:
        if parent == ROOT.parent:
            break
        if parent.exists() or parent.is_symlink():
            if parent.is_symlink() or getattr(parent.lstat(), "st_file_attributes", 0) & 0x400:
                raise ValueError(f"Linked path refused: {parent}")
    path.resolve().relative_to(ROOT.resolve())
    return path


def hashes(folder):
    result = {}
    for path in folder.rglob("*"):
        local(path)
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = sha(path)
    return result


def probe(name, argv, work, env, timeout):
    out, err = work / f"{name}.stdout.txt", work / f"{name}.stderr.txt"
    started = time.monotonic()
    timed_out = False
    with out.open("wb") as stdout, err.open("wb") as stderr:
        process = subprocess.Popen([str(a) for a in argv], cwd=work, env=env, shell=False,
                                   stdout=stdout, stderr=stderr,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            killer = shutil.which("taskkill") if os.name == "nt" else None
            if killer:
                subprocess.run([killer, "/PID", str(process.pid), "/T", "/F"], shell=False,
                               timeout=15, capture_output=True)
            process.kill()
            process.wait(timeout=15)
    return dict(name=name, argv=[str(a) for a in argv], exit_code=process.returncode,
                timed_out=timed_out, seconds=round(time.monotonic() - started, 3),
                stdout_sha256=sha(out), stderr_sha256=sha(err))


def measure_ignored_clearance(project, work, cli, timeout):
    """Measure identical copper with enabled/ignored clearance on a private copy."""
    target = work / "ignored-rule-project"
    shutil.copytree(project, target)
    pro = next(target.glob("*.kicad_pro"))
    pcb = next(target.glob("*.kicad_pcb"))
    settings = json.loads(pro.read_text(encoding="utf-8"))
    settings["board"]["design_settings"]["rules"]["min_clearance"] = 1.0
    rows = []
    for severity in ("error", "ignore"):
        settings["board"]["design_settings"]["rule_severities"]["clearance"] = severity
        pro.write_text(json.dumps(settings), encoding="utf-8")
        report = work / f"clearance-{severity}.json"
        output = run([cli, "pcb", "drc", pcb, "--format", "json", "--severity-all", "--output", report],
                     cwd=target, timeout=timeout)
        if output.returncode or not report.is_file():
            raise RuntimeError(f"Native clearance probe failed: {output.returncode}")
        data = json.loads(report.read_text(encoding="utf-8"))
        state = work / f"clearance-state-{severity}"
        state.mkdir()
        engine = Engine([pro], state)
        session = next(iter(engine.sessions.entries))
        before = revision(target)
        check = engine.call("check", dict(session=session, scope="pcb"))
        rows.append(dict(rule=severity, native_exit=output.returncode,
                         native_clearance=sum(r.get("type") == "clearance" for r in data.get("violations", [])),
                         native_ignored=data.get("ignored_checks"), pcbai_verified=check.get("verified"),
                         checks_run=check.get("checks_run"), revision_unchanged=revision(target) == before))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repos", type=Path, default=ROOT / ".pcbai-state/u0/repos")
    parser.add_argument("--output", type=Path, required=True, help="New development directory inside workspace")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 300:
        parser.error("timeout must be 1..300 seconds")
    work, repos = local(args.output), local(args.repos)
    if work.exists():
        parser.error("output must be new; previous evidence is never overwritten")
    python = os.environ.get("PCBAI_U0_PYTHON")
    if not python or not Path(python).is_file():
        parser.error("configure PCBAI_U0_PYTHON with the isolated dependency interpreter")
    git = shutil.which("git")
    if not git:
        parser.error("git must be available on PATH")
    sources = {}
    for name, pin in PINS.items():
        clone = local(repos / name)
        actual = run([git, "-C", clone, "rev-parse", "HEAD"], timeout=30)
        dirty = run([git, "-C", clone, "status", "--porcelain", "--untracked-files=no"], timeout=30)
        # eSim intentionally has no checkout; read its pinned objects only.
        if (actual.returncode or dirty.returncode or actual.stdout.strip() != pin
                or (name != "esim" and dirty.stdout.strip())):
            raise ValueError(f"Missing, modified or wrong upstream commit: {name}")
        sources[name] = dict(commit=pin, source=str(clone.relative_to(ROOT)))
    work.mkdir(parents=True)
    env = dict(os.environ)
    for key in list(env):
        if any(word in key.upper() for word in ("TOKEN", "SECRET", "API_KEY")):
            env.pop(key)
    home = work / "home"
    home.mkdir()
    env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home / "appdata"),
               LOCALAPPDATA=str(home / "localappdata"), XDG_CONFIG_HOME=str(home / "config"),
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    # Prevent inspector dotenv discovery from walking up to a user's .env file.
    (work / ".env").write_text("", encoding="utf-8")
    cli = find_kicad_cli()
    env["KICAD_CONFIG_HOME"] = str(private_kicad_config(cli, work / "kicad-config"))
    demo = Path(cli).resolve().parents[1] / "share/kicad/demos/ecc83"
    project = work / "project"
    shutil.copytree(demo, project)
    before = hashes(project)
    board = next(project.glob("*.kicad_pcb"))
    sch = next(project.glob("*.kicad_sch"))
    fab = work / "fab.zip"
    export_manifest = export_fab(project, board.name, fab, revision(project))
    rows = []

    def module(name, repo, mod, argv):
        source = repos / repo
        if repo in {"jbom", "inspector"}:
            source /= "src"
        rows.append(probe(name, [python, "-I", "-X", "utf8", "-c", BOOTSTRAP, source, mod, *argv],
                          work, env, args.timeout))

    module("jbom-help", "jbom", "jbom.cli.main", ["--help"])
    module("jbom-bom", "jbom", "jbom.cli.main", ["bom", sch, "-o", work / "bom.csv"])
    module("jbom-pos", "jbom", "jbom.cli.main", ["pos", board, "-o", work / "pos.csv"])
    broken = work / "broken.kicad_sch"
    broken.write_text("(broken", encoding="utf-8")
    module("jbom-broken", "jbom", "jbom.cli.main", ["bom", broken, "-o", work / "broken.csv"])
    module("dfm-help", "dfm", "pcb_dfm", ["--help"])
    module("dfm-fab", "dfm", "pcb_dfm", ["gate", fab, "--json", work / "dfm.json"])
    invalid_zip = work / "broken.zip"
    invalid_zip.write_bytes(b"invalid zip")
    module("dfm-broken", "dfm", "pcb_dfm", ["gate", invalid_zip, "--json", work / "dfm-broken.json"])
    module("inspector-help", "inspector", "pcb_inspector.cli.main", ["--help"])
    module("inspector-analyze", "inspector", "pcb_inspector.cli.main",
           ["analyze", board, "-f", "json", "-o", work / "inspector.json"])
    module("inspector-broken", "inspector", "pcb_inspector.cli.main",
           ["analyze", broken, "-f", "json", "-o", work / "inspector-broken.json"])
    broken_board = work / "invalid.kicad_pcb"
    broken_board.write_text("(broken", encoding="utf-8")
    module("inspector-broken-board", "inspector", "pcb_inspector.cli.main",
           ["analyze", broken_board, "-f", "json", "-o", work / "inspector-broken-board.json"])
    module("astra-help", "astra", "kicad.manufacturing", ["--help"])
    module("astra-fab", "astra", "kicad.manufacturing",
           ["--board", board, "--profile", repos / "astra/manufacturing.example.json",
            "--output", work / "astra-package", "--cli", cli])
    profile = work / "invalid-profile.json"
    profile.write_text('{"min_clearance_mm": -1}', encoding="utf-8")
    module("astra-broken", "astra", "kicad.manufacturing",
           ["--board", board, "--profile", profile, "--output", work / "astra-broken", "--cli", cli])
    for invalid in (False, True):
        label = "plugin-broken" if invalid else "plugin-bom"
        xml = work / (label + ".xml")
        xml.write_text("<broken" if invalid else
                       '<export><components><comp ref="R1"><value>10k</value><footprint>R_0603</footprint>'
                       '<fields><field name="Manufacturer">Example</field><field name="PartNumber">TEST</field>'
                       '<field name="Supplier">LCSC</field><field name="SupplierRef">C000</field>'
                       '</fields></comp></components></export>', encoding="utf-8")
        if not invalid:
            ET.parse(xml)
        rows.append(probe(label, [python, "-I", repos / "bom_cpl/bom-cpl-plugin.py", xml,
                                  work / label, "Quantity=2"], work, env, args.timeout))
    for name, program in (("hbee", "hauksbee"), ("esim", "esim")):
        binary = shutil.which(program)
        if binary:
            rows.append(probe(name + "-help", [binary, "--help"], work, env, args.timeout))
        else:
            rows.append(dict(name=name, status="not_run", reason="program_not_on_PATH",
                             toolchain_on_PATH=bool(shutil.which("cargo")) if name == "hbee" else None))
    freeze = probe("dependencies", [python, "-I", "-m", "pip", "freeze"], work, env, args.timeout)
    ignored = measure_ignored_clearance(project, work, cli, args.timeout)
    after = hashes(project)
    result = dict(sources=sources, commands=rows, dependencies=freeze, project_unchanged=before == after,
                  input_hashes=before, export_manifest=export_manifest, ignored_clearance=ignored,
                  scope="development smoke, not adapter/product/physical acceptance")
    (work / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(dict(project_unchanged=before == after, commands=rows), indent=2))
    return 0 if before == after and not any(row.get("timed_out") for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
