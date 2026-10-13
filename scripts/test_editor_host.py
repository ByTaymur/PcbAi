"""Exercise editor features from a built VSIX in a disposable real VS Code Host."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pcbai.external import find_kicad_cli, run

ROOT = Path(__file__).resolve().parents[1]


def stop_owned(service):
    if service is not None and service.poll() is None:
        service.terminate()
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            service.kill()
            service.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code', default=os.environ.get('PCBAI_CODE'))
    parser.add_argument('--full-libraries', action='store_true', help='Copy all installed symbols to the private corpus')
    args = parser.parse_args()
    code = args.code
    if not code:
        wrapper = shutil.which('code')
        code = str(Path(wrapper).parent.parent / 'Code.exe') if wrapper and os.name == 'nt' else None
    if not code or not Path(code).is_file():
        print('SKIP: configure PCBAI_CODE')
        return 77
    result_dir = ROOT / '.pcbai-state/eklenti-ozellikleri'
    result_dir.mkdir(parents=True, exist_ok=True)
    report = result_dir / ('editor-host-full-result.json' if args.full_libraries else 'editor-host-result.json')
    report.unlink(missing_ok=True)
    package = ROOT / 'vscode/pcbai-vscode'
    version = json.loads((package / 'package.json').read_text(encoding='utf-8'))['version']
    ir_assist = 'jsonValidation' in json.loads((package / 'package.json').read_text(encoding='utf-8'))['contributes']
    build = run([sys.executable, package / 'build_vsix.py'], cwd=ROOT, timeout=30)
    if build.returncode:
        print(build.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix='pcbai-editor-host-') as temporary:
        temp = Path(temporary)
        with zipfile.ZipFile(package / f'dist/pcbai-vscode-{version}.vsix') as archive:
            for entry in archive.infolist():
                path = (temp / 'vsix' / entry.filename).resolve()
                if not path.is_relative_to(temp / 'vsix') or entry.file_size > 64 * 1024 * 1024:
                    raise ValueError('Unsafe VSIX entry')
                if not entry.is_dir():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.read(entry))
        workspace = temp / 'project'
        workspace.mkdir()
        env = dict(os.environ, PCBAI_STATE_DIR=str(temp / 'state'), PCBAI_TEST_WORKSPACE=str(workspace),
                   PCBAI_HOST_RESULT=str(report), PCBAI_ROOT=str(ROOT), PCBAI_PYTHON=sys.executable)
        env.pop('ELECTRON_RUN_AS_NODE', None)
        service = None
        if ir_assist:
            demos = Path(find_kicad_cli()).parent.parent / 'share/kicad/demos'
            shutil.copytree(demos / 'ecc83', workspace, dirs_exist_ok=True)
            symbols = temp / 'symbols'
            symbols.mkdir()
            shutil.copyfile(demos.parent / 'symbols/Device.kicad_sym', symbols / 'Device.kicad_sym')
            if args.full_libraries:
                for source in (demos.parent / 'symbols').glob('*.kicad_sym'):
                    shutil.copyfile(source, symbols / source.name)
            library = symbols / 'Test.kicad_sym'
            library.write_text('''(kicad_symbol_lib (version 20231120) (generator "pcbai-test")
              (symbol "Multi" (property "Reference" "U") (property "Value" "Multi")
                (property "Description" "Private multi-unit fixture") (property "Footprint" "Test:Multi")
                (symbol "Multi_0_1" (pin passive line (at 0 0 0) (length 2.54) (name "COMMON") (number "01")))
                (symbol "Multi_1_1" (pin passive line (at 0 0 0) (length 2.54) (name "ONE") (number "1")))
                (symbol "Multi_2_1" (pin passive line (at 0 0 0) (length 2.54) (name "TWO") (number "2")))))''', encoding='utf-8')
            footprints = temp / 'footprints/Test.pretty'
            footprints.mkdir(parents=True)
            (footprints / 'Multi.kicad_mod').write_text('(footprint "Multi" (pad "01" smd rect (at 0 0) (size 1 1)) (pad "1" smd rect (at 2 0) (size 1 1)) (pad "2" smd rect (at 4 0) (size 1 1)))', encoding='utf-8')
            env.update(PYTHONPATH=str(ROOT), PCBAI_SYMBOLS=str(symbols), PCBAI_FOOTPRINTS=str(footprints.parent), PCBAI_TEST_LIBRARY=str(library))
            project = workspace / 'ecc83-pp.kicad_pro'
            service = subprocess.Popen([sys.executable, '-m', 'pcbai', 'serve', '--project', str(project)], cwd=ROOT,
                                       env=env, shell=False, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            deadline = time.monotonic() + 15
            while not (temp / 'state/service.json').is_file() and time.monotonic() < deadline and service.poll() is None:
                time.sleep(0.05)
            if not (temp / 'state/service.json').is_file():
                stop_owned(service)
                raise RuntimeError('Private service failed to become ready within 15 seconds')
            env.update(PCBAI_LIBRARY_FILES=str(len(list(symbols.glob('*.kicad_sym')))),
                       PCBAI_LIBRARY_BYTES=str(sum(p.stat().st_size for p in symbols.glob('*.kicad_sym'))))
            if args.full_libraries:
                # Warm only this owned service's index before the bounded Host acceptance run.
                connection = json.loads((temp / 'state/service.json').read_text(encoding='utf-8'))
                payload = json.dumps({'name': 'search_parts', 'arguments': {'query': 'resistor', 'limit': 1}}).encode()
                request = urllib.request.Request(f"http://127.0.0.1:{connection['port']}/call", data=payload,
                                                headers={'Authorization': 'Bearer ' + connection['token'], 'Content-Type': 'application/json'})
                started = time.monotonic()
                try:
                    with urllib.request.urlopen(request, timeout=120) as response:
                        preloaded = json.load(response)
                    if not preloaded.get('ok'):
                        raise RuntimeError('Private index preload failed')
                    env['PCBAI_PRELOAD_SECONDS'] = str(time.monotonic() - started)
                except Exception:
                    stop_owned(service)
                    raise
        try:
            output = run([code, workspace, '--user-data-dir', temp / 'profile', '--extensions-dir', temp / 'extensions',
                      '--disable-extensions', '--skip-welcome', '--skip-release-notes', '--disable-updates',
                      '--disable-gpu', '--new-window', '--disable-workspace-trust',
                      '--extensionDevelopmentPath=' + str(temp / 'vsix/extension'),
                      '--extensionTestsPath=' + str(package / 'test/editor_host.js')], cwd=ROOT, env=env, timeout=90)
        finally:
            stop_owned(service)
        if output.returncode or not report.exists():
            print(output.stdout[-3000:])
            print(output.stderr[-3000:])
            return 1
        print(report.read_text(encoding='utf-8'))
        return 0


if __name__ == '__main__':
    sys.exit(main())
