"""S11 development measurement only; never imports or vendors upstream code."""
import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pcbai.external import find_kicad_cli, find_kicad_python, run  # noqa: E402

DEMOS = ["ecc83", "pic_programmer", "video", "interf_u", "stickhub"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*")) if p.is_file()}


def reject_links(folder):
    """Do not follow source symlinks or Windows junction/reparse points."""
    for path in [folder, *folder.rglob("*")]:
        if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("Linked input is not allowed: " + str(path))
        path.resolve().relative_to(folder.resolve())


def peak_memory(process):
    """Windows kernel peak working set (bytes), not a polling estimate."""
    if os.name != "nt":
        return None

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    api = ctypes.WinDLL("psapi").GetProcessMemoryInfo
    api.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    api.restype = ctypes.c_int
    return counters.PeakWorkingSetSize if api(int(process._handle), ctypes.byref(counters), counters.cb) else None


def measure(argv, cwd, output, timeout):
    started = time.perf_counter()
    stderr = output.with_suffix(".stderr.txt")
    with output.open("wb") as out, stderr.open("wb") as err:
        process = subprocess.Popen([str(a) for a in argv], cwd=cwd, stdout=out, stderr=err, shell=False,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait(timeout=10)
        peak = peak_memory(process)
    return dict(argv=[str(a) for a in argv], cwd=str(cwd), seconds=time.perf_counter() - started,
                exit_code=process.returncode, timed_out=timed_out, peak_working_set_bytes=peak,
                output_sha256=sha(output), output=str(output.relative_to(ROOT)),
                stderr=str(stderr.relative_to(ROOT)))


def oracle_netlist(path):
    root = ET.parse(path).getroot()
    components = {c.attrib["ref"] for c in root.findall("./components/comp")}
    nets = {n.attrib["name"]: sorted((p.attrib["ref"], p.attrib["pin"]) for p in n.findall("node"))
            for n in root.findall("./nets/net")}
    return dict(components=sorted(components), nets=nets)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clone", type=Path, default=ROOT / ".pcbai-state/s11/kicad-happy")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--demos", nargs="+", choices=DEMOS, default=DEMOS)
    args = parser.parse_args()
    work = ROOT / ".pcbai-state/s11"
    work.resolve().relative_to(ROOT)
    work.mkdir(parents=True, exist_ok=True)
    clone = args.clone.resolve()
    clone.relative_to(work.resolve())
    reject_links(args.clone.absolute())
    commit = run(["git", "-C", clone, "rev-parse", "HEAD"], timeout=20).stdout.strip()
    scripts = clone / "skills/kicad/scripts"
    cli, python = find_kicad_cli(), find_kicad_python()
    demos = Path(cli).parent.parent / "share/kicad/demos"
    result = dict(commit=commit, license_sha256=sha(clone / "LICENSE"), cli=cli, python=python,
                  python_version=run([python, "-I", "--version"], timeout=20).stdout.strip(),
                  cli_version=run([cli, "--version"], timeout=20).stdout.strip(), records=[])
    for demo in args.demos:
        folder = demos / demo
        reject_links(folder)
        before = hashes(folder)
        projects = sorted(folder.glob("*.kicad_pro"))
        project = next((p for p in projects if p.stem == demo), projects[0])
        record = dict(demo=demo, source_before=before, runs=[])
        with tempfile.TemporaryDirectory(prefix=f"{demo}-", dir=work) as tmp:
            scratch = Path(tmp)
            shutil.copytree(folder, scratch / "project")
            copied = scratch / "project" / project.name
            netlist = work / f"{demo}-netlist.xml"
            exported = run([cli, "sch", "export", "netlist", copied.with_suffix(".kicad_sch"),
                            "--format", "kicadxml", "--output", netlist], cwd=scratch, timeout=args.timeout)
            record["netlist_export"] = dict(exit_code=exported.returncode, stdout=exported.stdout,
                                            stderr=exported.stderr)
            if not exported.returncode:
                record["oracle_schematic"] = oracle_netlist(netlist)
            for kind, suffix in [("schematic", ".kicad_sch"), ("pcb", ".kicad_pcb")]:
                for repetition in (1, 2):
                    output = work / f"{demo}-{kind}-{repetition}.json"
                    measured = measure([python, "-I", "-B", "-X", "utf8", scripts / f"analyze_{kind}.py",
                                        copied.with_suffix(suffix)], scratch, output, args.timeout)
                    measured.update(kind=kind, repetition=repetition)
                    if not measured["exit_code"]:
                        data = json.loads(output.read_text(encoding="utf-8"))
                        findings = data.get("findings", [])
                        measured.update(statistics=data.get("statistics"), findings=len(findings),
                                        finding_ids=sorted(f["finding_id"] for f in findings),
                                        detectors=dict(Counter(f.get("detector", "missing") for f in findings)),
                                        confidence=dict(Counter(f.get("confidence", "missing") for f in findings)))
                    record["runs"].append(measured)
                    print(f"{demo} {kind} {repetition}: exit={measured['exit_code']} "
                          f"{measured['seconds']:.3f}s", flush=True)
            pcb_oracle = work / f"{demo}-pcb-oracle.json"
            record["pcb_oracle_run"] = measure(
                [python, "-I", "-X", "utf8", ROOT / "scripts/s11_pcb_oracle.py",
                 copied.with_suffix(".kicad_pcb")], scratch, pcb_oracle, args.timeout)
            if not record["pcb_oracle_run"]["exit_code"]:
                record["oracle_pcb"] = json.loads(pcb_oracle.read_text(encoding="utf-8"))
        record["source_after"] = hashes(folder)
        record["source_preserved"] = record["source_before"] == record["source_after"]
        result["records"].append(record)
        (work / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(r["source_preserved"] and all(not x["exit_code"] for x in r["runs"])
                    for r in result["records"]) else 1


if __name__ == "__main__":
    sys.exit(main())
