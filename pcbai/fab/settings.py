"""Disposable native KiCad reader with private configuration and bounded output."""
import json
import os
import tempfile
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli, find_kicad_python, private_kicad_config, run
from pcbai.fab.profile import KEYS, number


def native_defaults(root, document):
    with tempfile.TemporaryDirectory(prefix="pcbai-profile-config-") as temporary:
        private = private_kicad_config(find_kicad_cli(), temporary)
        output = run([find_kicad_python(), "-I", "-X", "utf8", Path(__file__).with_name("settings_worker.py"), Path(root) / document],
                     cwd=root, timeout=30, env=dict(os.environ, KICAD_CONFIG_HOME=str(private)))
    if output.returncode or len(output.stdout) > 16384:
        raise PcbAiError("profile_defaults_unavailable", "Native KiCad settings could not be measured")
    try:
        values = json.loads(output.stdout)
        if not isinstance(values, dict) or set(values) != KEYS:
            raise ValueError("Incomplete native settings")
        return {key: number(value) for key, value in values.items()}
    except (ValueError, TypeError) as exc:
        raise PcbAiError("profile_defaults_unavailable", "Native settings report is invalid") from exc
