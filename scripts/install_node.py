"""Install a checksum-verified, project-local Node 22 on Windows; no registry/PATH changes."""
import hashlib
import io
import os
import urllib.request
import zipfile
from pathlib import Path

VERSION = "22.23.3"
SHA256 = "2b0ff57b049cda1bbcea2240eec20467018713c1efe1f7360c2681859b90ed71"
ROOT = Path(__file__).resolve().parents[1]


def main():
    if os.name != "nt":
        raise SystemExit("Use Node 22 from PATH or PCBAI_NODE on non-Windows systems")
    name = f"node-v{VERSION}-win-x64"
    with urllib.request.urlopen(f"https://nodejs.org/dist/v{VERSION}/{name}.zip", timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit("Node archive SHA-256 mismatch")
    destination = ROOT / ".tools/node"
    if not destination.resolve().is_relative_to(ROOT):
        raise SystemExit("Node destination escapes the checkout")
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for entry in archive.infolist():
            relative = Path(entry.filename).relative_to(name)
            path = destination / relative
            if not path.resolve().is_relative_to(destination.resolve()):
                raise SystemExit("Unsafe Node archive path")
            if entry.is_dir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.read(entry))
    print(destination / "node.exe")
    print(f"Node {VERSION}; verified SHA-256 {SHA256}")


if __name__ == "__main__":
    main()
