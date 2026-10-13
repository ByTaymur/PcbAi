"""Keep development/audit runs out of the published evidence directory."""
from pathlib import Path

from kicad_plugin.configure import assert_unlinked


def report_path(root, name, *, publish=False, output=None):
    root = Path(root).resolve()
    base = root / ('docs/spikes' if publish else '.pcbai-state')
    path = Path(output).absolute() if output else base / name
    assert_unlinked(path)
    path = path.resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError('Kanıt çıktısı .pcbai-state altında olmalı; docs/spikes için --publish gerekir.')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
