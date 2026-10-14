import json
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from pcbai.external import find_kicad_cli, run

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / 'vscode/pcbai-vscode'


class DruTests(unittest.TestCase):
    def test_real_kicad_accepts_snippets_and_rejects_invalid_rule(self):
        try:
            cli = Path(find_kicad_cli())
        except Exception:
            self.skipTest('KiCad CLI unavailable')
        demo = cli.parent.parent / 'share/kicad/demos/ecc83'
        if not demo.is_dir():
            self.skipTest('KiCad ecc83 corpus unavailable')
        snippets = json.loads((EXT / 'snippets/kicad-dru.json').read_text(encoding='utf-8'))
        bodies = [re.sub(r'\$\d+', '', re.sub(r'\$\{\d+:([^}]+)\}', r'\1', '\n'.join(s['body']))) for s in snippets.values()]
        with tempfile.TemporaryDirectory(prefix='pcbai-dru-') as temporary:
            root = Path(temporary) / 'project'
            shutil.copytree(demo, root)
            board = next(root.glob('*.kicad_pcb'))
            rules = board.with_suffix('.kicad_dru')
            sentinel = '\n(rule "pcbai loading probe" (constraint clearance (min 10mm)))'
            rules.write_text('(version 1)\n' + '\n'.join(bodies) + sentinel, encoding='utf-8')
            checked = run([cli, 'pcb', 'drc', board, '--format', 'json', '--output', root / 'valid.json'], cwd=root, timeout=60)
            evidence = ROOT / '.pcbai-state/eklenti-ozellikleri'
            evidence.mkdir(parents=True, exist_ok=True)
            (evidence / 'dru-valid.json').write_bytes((root / 'valid.json').read_bytes())
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertTrue((root / 'valid.json').is_file())
            self.assertIn('pcbai loading probe', (root / 'valid.json').read_text(encoding='utf-8'),
                          'KiCad discarded snippet rules; success exit alone is not syntax acceptance')
            rules.write_text('(version 1)\n(rule "broken" (constraint clearance (min 0.2mm))', encoding='utf-8')
            broken = run([cli, 'pcb', 'drc', board, '--format', 'json', '--output', root / 'invalid.json'], cwd=root, timeout=60)
            (evidence / 'dru-invalid.json').write_bytes((root / 'invalid.json').read_bytes())
            (evidence / 'dru-cli-output.json').write_text(json.dumps({'valid': [checked.returncode, checked.stdout, checked.stderr], 'invalid': [broken.returncode, broken.stdout, broken.stderr]}, indent=2), encoding='utf-8')
            if broken.returncode == 0:
                rules.write_text('(version 1)\n(rule "pcbai loading probe" (constraint clearance (min 10mm)))', encoding='utf-8')
                loaded = run([cli, 'pcb', 'drc', board, '--format', 'json', '--output', root / 'loading.json'], cwd=root, timeout=60)
                self.assertEqual(loaded.returncode, 0, loaded.stderr)
                report = (root / 'loading.json').read_text(encoding='utf-8')
                (evidence / 'dru-loading-probe.json').write_text(report, encoding='utf-8')
                if 'pcbai loading probe' not in report:
                    self.skipTest('CLI did not demonstrate loading custom DRU rules (10mm probe absent); syntax acceptance unavailable')
                # KiCad 10.0.x drops a malformed file and exits 0; PcbAi's gate must reject it instead.
                from pcbai.core.contract import PcbAiError
                from pcbai.kicad.cli import rule_check
                rules.write_text('(version 1)\n(rule "broken" (constraint clearance (min 0.2mm))', encoding='utf-8')
                with self.assertRaises(PcbAiError) as raised:
                    rule_check(root, board.name, 'drc')
                self.assertEqual(raised.exception.code, 'custom_rules_invalid')
                return
            self.assertNotEqual(broken.returncode, 0, broken.stdout + broken.stderr)

    def test_vsix_contains_all_declared_language_assets(self):
        import sys
        built = run([sys.executable, EXT / 'build_vsix.py'], cwd=ROOT, timeout=30)
        self.assertEqual(built.returncode, 0, built.stderr)
        manifest = json.loads((EXT / 'package.json').read_text(encoding='utf-8'))
        with zipfile.ZipFile(EXT / f"dist/pcbai-vscode-{manifest['version']}.vsix") as package:
            for section, key in [('languages', 'configuration'), ('grammars', 'path'), ('snippets', 'path')]:
                for entry in manifest['contributes'][section]:
                    self.assertIn('extension/' + entry[key].removeprefix('./'), package.namelist())
            self.assertEqual(json.loads(package.read('extension/package.json'))['version'], manifest['version'])
            if 'jsonValidation' in manifest['contributes']:
                self.assertEqual(package.read('extension/schemas/circuit.schema.json'), (ROOT / 'pcbai/ir/circuit.schema.json').read_bytes())
                self.assertIn('extension/part_assist.js', package.namelist())
