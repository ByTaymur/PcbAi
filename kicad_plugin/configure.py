"""Record a checkout outside the plugin package; does not change KiCad settings."""
import argparse
import json
import os
import stat
from pathlib import Path


def assert_unlinked(path):
    """Refuse symbolic links and Windows reparse points in a write target's ancestry."""
    for entry in (path, *path.parents):
        if entry.is_symlink() or (entry.exists() and getattr(entry.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError(f"Bağlantı/junction üzerinden yazım reddedildi: {entry}")
        if entry.exists():
            info = entry.lstat()
            if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
                raise ValueError(f"Hardlink üzerinden yazım reddedildi: {entry}")


def configure(root, location=None):
    root = Path(root).resolve()
    if not all((root / name).is_file() for name in ("mcp_server/client.py", "pcbai/__init__.py")):
        raise ValueError(f"PcbAi deposu bulunamadı: {root}")
    location = (Path(location) if location is not None else
                Path(os.environ.get('APPDATA', Path.home() / '.config')) / 'PcbAi/location.json')
    location = location.absolute()
    assert_unlinked(location)
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(json.dumps({'root': str(root)}, ensure_ascii=False, indent=2), encoding='utf-8')
    return location


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--location', type=Path, help='Override the external location file (e.g. isolated tests)')
    args = parser.parse_args()
    print(configure(args.root, args.location))


if __name__ == '__main__':
    main()
