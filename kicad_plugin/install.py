"""Install the PcbAi IPC plugin into KiCad 10 (standard library only).

    python kicad_plugin/install.py [--dest <KiCad plugins folder>]

Development only: copies to <Documents>/KiCad/10.0/plugins/org.pcbai.kicad.
For normal installation use build_pcm.py and PCM's Install from File. The checkout path is stored outside
the plugin in the user's PcbAi/location.json file. Do not use beside a PCM install of the same identifier.
KiCad's API server must be enabled (Preferences → Plugins → Enable KiCad API); this script does not change
KiCad settings. KiCad creates the plugin's Python environment and installs requirements.txt on first use.
"""
import argparse
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kicad_plugin.configure import assert_unlinked, configure

HERE = Path(__file__).resolve().parent
IDENTIFIER = "org.pcbai.kicad"
FILES = ["plugin.json", "requirements.txt", "pcbai_kicad.py", "register.py", "check.py"]


def png(size, pixel):
    rows = b"".join(b"\0" + b"".join(bytes(pixel(x / size, y / size)) for x in range(size)) for y in range(size))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def icon(color, mark):
    def pixel(u, v):
        inside = 0.08 <= u <= 0.92 and 0.08 <= v <= 0.92
        if not inside:
            return (0, 0, 0, 0)
        return (255, 255, 255, 255) if mark(u, v) else (*color, 255)
    return pixel


def plus(u, v):
    return (0.44 <= u <= 0.56 and 0.24 <= v <= 0.76) or (0.44 <= v <= 0.56 and 0.24 <= u <= 0.76)


def tick(u, v):
    first = 0.25 <= u <= 0.45 and abs(v - (0.52 + (u - 0.25))) < 0.075
    second = 0.42 <= u <= 0.78 and abs(v - (0.72 - (u - 0.42) * 1.2)) < 0.075
    return first or second


def install(dest, location=None):
    dest = Path(dest).absolute()
    if not dest.parent.is_dir():
        raise ValueError(f"KiCad 10 belge klasörü yok: {dest.parent}. --dest ile verin.")
    target = dest / IDENTIFIER
    assert_unlinked(target)
    entries = {name: (HERE / name).read_bytes() for name in FILES}
    entries['LICENSE'] = (HERE.parent / 'LICENSE').read_bytes()
    for name, color, mark in (("register", (37, 99, 235), plus), ("check", (22, 163, 74), tick)):
        for size in (24, 48):
            entries[f'icons/{name}-{size}.png'] = png(size, icon(color, mark))
    for name in [*entries, 'pcbai_location.json']:
        assert_unlinked(target / name)
    configure(HERE.parent, location)
    for name, data in entries.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (target / 'pcbai_location.json').unlink(missing_ok=True)
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, default=Path.home() / "Documents" / "KiCad" / "10.0" / "plugins")
    parser.add_argument('--location', type=Path, help='External PcbAi location file')
    args = parser.parse_args()
    print(install(args.dest, args.location))


if __name__ == "__main__":
    main()
