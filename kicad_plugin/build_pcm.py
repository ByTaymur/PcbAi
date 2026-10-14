"""Build a portable KiCad 10 IPC PCM archive using only the standard library."""
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pcbai import __version__
from kicad_plugin.install import FILES, ICONS, IDENTIFIER, icon, plus, png

ROOT = Path(__file__).resolve().parent.parent
LICENSE = 'LGPL-2.1-or-later'


def metadata():
    return {
        '$schema': 'https://go.kicad.org/pcm/schemas/v2',
        'name': 'PcbAi',
        'description': 'KiCad projelerini PcbAi servisine kaydet, ERC/DRC çalıştır ve PcbAi Asistan ile ajanlara istek gönder.',
        'description_full': 'KiCad 10 IPC eklentisi. PcbAi deposu ve Python ortamı ayrı kurulur. '
                            'Konum: PCBAI_ROOT veya kullanıcı PcbAi/location.json dosyası. '
                            'İlk kullanımda kicad-python kurulumu internet ister. '
                            'Denetimler kaydedilmiş dosyalarda çalışır.',
        'identifier': IDENTIFIER,
        'type': 'plugin',
        'author': {'name': 'Taymur', 'contact': {}},
        'license': LICENSE,
        'resources': {},
        'versions': [{'version': __version__, 'status': 'development', 'kicad_version': '10.0.7', 'runtime': 'ipc'}],
    }


def build(output=None):
    output = Path(output) if output else ROOT / f'kicad_plugin/dist/pcbai-kicad-{__version__}.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    entries = {'metadata.json': json.dumps(metadata(), ensure_ascii=False, indent=2).encode('utf-8'),
               'resources/icon.png': png(64, icon((37, 99, 235), plus)),
               'plugins/LICENSE': (ROOT / 'LICENSE').read_bytes()}
    for name in FILES:
        entries['plugins/' + name] = (ROOT / 'kicad_plugin' / name).read_bytes()
    for name, color, mark in ICONS:
        for size in (24, 48):
            entries[f'plugins/icons/{name}-{size}.png'] = png(size, icon(color, mark))
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return output


if __name__ == '__main__':
    print(build())
