import json
import os
import shutil
import struct
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from kicad_plugin import pcbai_kicad
from kicad_plugin.build_pcm import build, metadata
from kicad_plugin.configure import configure
from kicad_plugin.install import install
from pcbai import __version__
from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli, run

ROOT = Path(__file__).resolve().parents[1]


class KiCadPluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pcbai-plugin-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def checkout(self, name):
        root = self.root / name
        for filename in ('mcp_server/client.py', 'pcbai/__init__.py'):
            path = root / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# isolated root discovery fixture', encoding='utf-8')
        return root

    def test_portable_reproducible_package_and_action_resources(self):
        one = build(self.root / 'one.zip')
        two = build(self.root / 'two.zip')
        self.assertEqual(one.read_bytes(), two.read_bytes())
        with zipfile.ZipFile(one) as package:
            names = package.namelist()
            self.assertFalse(any('location' in name or name.endswith('install.py') for name in names))
            data = json.loads(package.read('metadata.json'))
            self.assertEqual(data['versions'][0]['runtime'], 'ipc')
            self.assertEqual(data['versions'][0]['version'], __version__)
            self.assertEqual(data['identifier'], 'org.pcbai.kicad')
            self.assertEqual(struct.unpack('>II', package.read('resources/icon.png')[16:24]), (64, 64))
            self.assertIn(b'LGPL-2.1-or-later', package.read('plugins/LICENSE'))
            plugin = json.loads(package.read('plugins/plugin.json'))
            for action in plugin['actions']:
                self.assertIn('plugins/' + action['entrypoint'], names)
                for icon in action['icons-light'] + action['icons-dark']:
                    self.assertIn('plugins/' + icon, names)
            for name in names:
                self.assertFalse(name.startswith('/') or '..' in Path(name).parts)
                self.assertNotIn(str(ROOT).encode(), package.read(name))

    def test_package_relocates_to_two_checkouts_in_fresh_plugin_processes(self):
        import sys
        with zipfile.ZipFile(build(self.root / 'plugin.zip')) as package:
            package.extractall(self.root / 'unpacked')
        script = """import os
from pathlib import Path
import pcbai_kicad
print(pcbai_kicad.pcbai_root())
client = pcbai_kicad.client_for(Path(os.environ['PCBAI_TEST_PROJECT']))
try:
    session = pcbai_kicad.session_for(client, Path(os.environ['PCBAI_TEST_PROJECT']))
    assert Path(session['root']) == Path(os.environ['PCBAI_TEST_PROJECT']).parent
    assert client._request('GET', '/health')['name'] == 'pcbai'
finally:
    client.shutdown()
    client.started_process.wait(timeout=10)
"""
        from tests.helpers import make_project
        project = make_project(self.root / 'project')
        for name in ('checkout-one', 'checkout-two'):
            checkout = self.root / name
            for folder in ('pcbai', 'mcp_server'):
                shutil.copytree(ROOT / folder, checkout / folder, ignore=shutil.ignore_patterns('__pycache__'))
            location = self.root / 'config/PcbAi/location.json'
            configure(checkout, location)
            env = dict(os.environ, APPDATA=str(location.parent.parent),
                       PCBAI_STATE_DIR=str(self.root / ('state-' + name)),
                       PCBAI_SERVICE_PYTHON=sys.executable, PCBAI_TEST_PROJECT=str(project))
            env.pop('PCBAI_ROOT', None)
            response = run([sys.executable, '-c', script], cwd=self.root / 'unpacked/plugins',
                           env=env, timeout=30)
            self.assertEqual(response.returncode, 0, response.stderr)
            self.assertEqual(response.stdout.strip(), str(checkout.resolve()))

    def test_explicit_root_precedence_and_invalid_setting_does_not_fall_back(self):
        first, second = self.checkout('one'), self.checkout('two')
        config = self.root / 'config/PcbAi/location.json'
        configure(first, config)
        with patch.dict(os.environ, APPDATA=str(config.parent.parent), PCBAI_ROOT=str(second)):
            self.assertEqual(pcbai_kicad.pcbai_root(), second.resolve())
        for bad in ('relative/root', str(self.root / 'missing')):
            with patch.dict(os.environ, APPDATA=str(config.parent.parent), PCBAI_ROOT=bad):
                with self.assertRaises(RuntimeError):
                    pcbai_kicad.pcbai_root()

    def test_missing_or_bad_configuration_explains_recovery(self):
        config = self.root / 'config/PcbAi/location.json'
        config.parent.mkdir(parents=True)
        for data in (None, '{', '[]', '{"root": null}', '{"root": "relative"}'):
            if data is not None:
                config.write_text(data, encoding='utf-8')
            with patch.dict(os.environ, APPDATA=str(config.parent.parent)):
                with patch.dict(os.environ, {'PCBAI_ROOT': ''}):
                    with self.assertRaisesRegex(RuntimeError, 'PCBAI_ROOT'):
                        pcbai_kicad.pcbai_root()

    def test_development_install_uses_external_location_and_preserves_other_files(self):
        dest = self.root / 'KiCad/plugins'
        dest.mkdir(parents=True)
        target = dest / 'org.pcbai.kicad'
        target.mkdir()
        (target / 'unrelated.txt').write_text('preserve', encoding='utf-8')
        (target / 'pcbai_location.json').write_text('{}', encoding='utf-8')
        config = self.root / 'config/PcbAi/location.json'
        self.assertEqual(install(dest, config), target)
        self.assertFalse((target / 'pcbai_location.json').exists())
        self.assertEqual((target / 'unrelated.txt').read_text(), 'preserve')
        self.assertEqual(json.loads(config.read_text())['root'], str(ROOT))

    def test_development_install_refuses_junction_without_touching_target(self):
        if os.name != 'nt':
            self.skipTest('Windows junction acceptance')
        from pcbai.external import run
        dest = self.root / 'KiCad/plugins'
        dest.mkdir(parents=True)
        outside = self.root / 'outside'
        outside.mkdir()
        sentinel = outside / 'sentinel.txt'
        sentinel.write_text('preserve', encoding='utf-8')
        junction = dest / 'org.pcbai.kicad'
        response = run(['cmd', '/c', 'mklink', '/J', str(junction), str(outside)], timeout=10)
        self.assertEqual(response.returncode, 0, response.stderr)
        try:
            with self.assertRaises(ValueError):
                install(dest, self.root / 'config/location.json')
            self.assertEqual(sentinel.read_text(), 'preserve')
            self.assertEqual(list(outside.iterdir()), [sentinel])
        finally:
            junction.rmdir()

    def test_license_consistent_across_manifests(self):
        expected = 'LGPL-2.1-or-later'
        self.assertEqual(metadata()['license'], expected)
        for filename in ('kicad_plugin/plugin.json', 'vscode/pcbai-vscode/package.json'):
            self.assertEqual(json.loads((ROOT / filename).read_text(encoding='utf-8'))['license'], expected)
        project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
        self.assertEqual(project['project']['license']['text'], expected)
        self.assertIn(expected, (ROOT / 'LICENSE').read_text(encoding='utf-8'))

    def test_installer_and_config_refuse_hardlinks_without_mutating_other_file(self):
        sentinel = self.root / 'sentinel'
        sentinel.write_text('preserve', encoding='utf-8')
        dest = self.root / 'KiCad/plugins'
        target = dest / 'org.pcbai.kicad'
        target.mkdir(parents=True)
        os.link(sentinel, target / 'register.py')
        with self.assertRaisesRegex(ValueError, 'Hardlink'):
            install(dest, self.root / 'location.json')
        location = self.root / 'location.json'
        os.link(sentinel, location)
        with self.assertRaisesRegex(ValueError, 'Hardlink'):
            configure(ROOT, location)
        self.assertEqual(sentinel.read_text(), 'preserve')

    def test_official_installed_pcm_and_api_schemas(self):
        try:
            cli = Path(find_kicad_cli())
        except PcbAiError as exc:
            self.skipTest(str(exc))
        schemas = cli.parent.parent / 'share/kicad/schemas'
        if not (schemas / 'pcm.v2.schema.json').is_file():
            self.skipTest('Installed KiCad PCM v2 schema unavailable')
        from jsonschema import Draft7Validator
        pcm = Draft7Validator(json.loads((schemas / 'pcm.v2.schema.json').read_text(encoding='utf-8')))
        pcm.validate(metadata())
        invalid = metadata()
        del invalid['license']
        self.assertFalse(pcm.is_valid(invalid))
        api = Draft7Validator(json.loads((schemas / 'api.v1.schema.json').read_text(encoding='utf-8')))
        api.validate(json.loads((ROOT / 'kicad_plugin/plugin.json').read_text(encoding='utf-8')))

    def test_missing_kipy_has_installation_hint(self):
        def unavailable():
            raise ModuleNotFoundError("No module named kipy", name='kipy')
        with patch.object(pcbai_kicad, 'message') as message:
            pcbai_kicad.run(unavailable)
        self.assertIn('internet', message.call_args.args[0])
        self.assertTrue(message.call_args.kwargs['error'])
