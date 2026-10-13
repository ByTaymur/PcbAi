"""Install the locally built VSIX using the configured/PATH VS Code CLI, without a shell."""
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pcbai.external import run

ROOT = Path(__file__).resolve().parents[1]


def main():
    package = json.loads((ROOT / "vscode/pcbai-vscode/package.json").read_text(encoding="utf-8"))
    artifact = ROOT / f"vscode/pcbai-vscode/dist/pcbai-vscode-{package['version']}.vsix"
    configured = os.environ.get("PCBAI_CODE")
    wrapper = shutil.which("code")
    executable = Path(configured) if configured else Path(wrapper).parent.parent / "Code.exe" if wrapper else None
    if os.name != "nt" or executable is None or not executable.is_file():
        raise SystemExit("Use your platform's code --install-extension, or configure PCBAI_CODE on Windows")
    cli = executable.parent / "resources/app/out/cli.js"
    configured_cli = os.environ.get("PCBAI_CODE_CLI")
    if configured_cli:
        cli = Path(configured_cli)
    elif not cli.is_file() and wrapper:
        # Read the literal script location as data; never execute/interpolate the batch file.
        text = Path(wrapper).read_text(encoding="utf-8")
        match = re.search(r'"%~dp0\.\.\\([^"%]*\\resources\\app\\out\\cli\.js)"', text)
        if match:
            candidate = (Path(wrapper).parent.parent / match.group(1)).resolve()
            if candidate.is_relative_to(Path(wrapper).parent.parent.resolve()):
                cli = candidate
    if not cli.is_file() or not artifact.is_file():
        raise SystemExit("VS Code CLI or built VSIX is missing")
    env = dict(os.environ, ELECTRON_RUN_AS_NODE="1")
    for args in [["--install-extension", str(artifact), "--force"], ["--list-extensions", "--show-versions"]]:
        response = run([executable, cli, *args], env=env, timeout=60)
        if response.returncode:
            raise SystemExit(response.stderr)
        if args[0] == "--install-extension":
            print(response.stdout.strip())
        else:
            expected = f"{package['publisher']}.{package['name']}@{package['version']}"
            if expected not in response.stdout.splitlines():
                raise SystemExit("Installed VS Code version was not verified")
            print(expected)


if __name__ == "__main__":
    main()
