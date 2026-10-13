import os
import shutil
import unittest
from pathlib import Path

from pcbai.external import run


def node_runtime():
    configured = os.environ.get("PCBAI_NODE") or shutil.which("node")
    if configured:
        return configured, False
    code = shutil.which("code")
    if os.name == "nt" and code:
        electron = Path(code).parent.parent / "Code.exe"
        if electron.is_file():
            return str(electron), True
    return None


class VSCodeTests(unittest.TestCase):
    def test_audit_evidence_link_boundaries(self):
        runtime = node_runtime()
        if runtime is None:
            self.skipTest('Node or VS Code Electron runtime not configured/on PATH')
        executable, electron = runtime
        env = dict(os.environ)
        if electron:
            env['ELECTRON_RUN_AS_NODE'] = '1'
        script = Path(__file__).resolve().parents[1] / 'vscode/pcbai-vscode/test/test_evidence_output.js'
        process = run([executable, script], env=env, timeout=20)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn('Published evidence protected', process.stdout)

    def test_preview_commands_and_webview_boundary(self):
        runtime = node_runtime()
        if runtime is None:
            self.skipTest("Node or VS Code Electron runtime not configured/on PATH")
        executable, electron = runtime
        env = dict(os.environ)
        if electron:
            env["ELECTRON_RUN_AS_NODE"] = "1"
        script = Path(__file__).resolve().parents[1] / "vscode/pcbai-vscode/test_extension.js"
        process = run([executable, script], env=env, timeout=20)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("text escaping passed", process.stdout)
