"""AJ-S1 deneme düğmesini ayrı identifier (org.pcbai.ajs1) ile kur / kaldır. PCM kurulumuna dokunmaz.

    python scripts/spikes/ajs1/install_ajs1.py [--dest <KiCad 10 plugins>] [--remove]
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from kicad_plugin.install import icon, png, plus  # noqa: E402

IDENTIFIER = "org.pcbai.ajs1"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dest", type=Path, default=Path.home() / "Documents" / "KiCad" / "10.0" / "plugins")
    p.add_argument("--remove", action="store_true")
    a = p.parse_args()
    target = a.dest.absolute() / IDENTIFIER
    if a.remove:
        shutil.rmtree(target, ignore_errors=True)
        print("removed", target)
        return
    target.mkdir(parents=True, exist_ok=True)
    for name in ("plugin.json", "ajs1_action.py"):
        shutil.copyfile(HERE / "plugin" / name, target / name)
    (target / "requirements.txt").write_text("kicad-python>=0.8.0\n", encoding="utf-8")
    for size in (24, 48):
        (target / "icons").mkdir(exist_ok=True)
        (target / "icons" / f"ajs1-{size}.png").write_bytes(png(size, icon((217, 119, 6), plus)))
    (target / "ajs1_location.json").write_text(json.dumps({
        "window": str(HERE / "ajs1_window.py"),
        "state_dir": str(ROOT / ".pcbai-state" / "ajs1")}), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
