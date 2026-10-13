"""Run real VS Code webview acceptance with a disposable profile, extensions and state."""

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pcbai.external import run, find_kicad_cli
from scripts.evidence_output import report_path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true', help='Explicitly replace published G0 evidence')
    args = parser.parse_args()
    configured = os.environ.get("PCBAI_CODE")
    executable = Path(configured) if configured else None
    if executable is None:
        wrapper = shutil.which("code")
        if os.name == "nt" and wrapper:
            executable = Path(wrapper).parent.parent / "Code.exe"
    if executable is None or not executable.is_file():
        print("SKIP: configure PCBAI_CODE or install VS Code on PATH")
        return 77
    report = report_path(ROOT, 'G0-host-result.json', publish=args.publish)
    report.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="pcbai-host-") as temporary:
        temp = Path(temporary)
        demo = Path(find_kicad_cli()).parent.parent / "share/kicad/demos/ecc83"
        workspace = temp / "project"
        shutil.copytree(demo, workspace)
        env = dict(os.environ, PCBAI_STATE_DIR=str(temp / "state"), PCBAI_HOST_RESULT=str(report),
                   PCBAI_ROOT=str(ROOT), PCBAI_PYTHON=sys.executable)
        env.pop("ELECTRON_RUN_AS_NODE", None)
        args = [
            executable,
            workspace,
            "--user-data-dir",
            temp / "profile",
            "--extensions-dir",
            temp / "extensions",
            "--disable-extensions",
            "--skip-welcome",
            "--skip-release-notes",
            "--disable-workspace-trust",
            "--disable-updates",
            "--disable-gpu",
            "--new-window",
            "--extensionDevelopmentPath=" + str(ROOT / "vscode/pcbai-vscode"),
            "--extensionTestsPath=" + str(ROOT / "vscode/pcbai-vscode/test/host.js"),
        ]
        result = run(args, env=env, timeout=90, cwd=ROOT)
        if result.returncode or not report.exists():
            print(result.stdout[-4000:])
            print(result.stderr[-4000:])
            return 1
        print(report.read_text())
        return 0


if __name__ == "__main__":
    sys.exit(main())
