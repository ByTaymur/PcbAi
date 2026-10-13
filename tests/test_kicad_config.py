import hashlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli, private_kicad_config, run


def cli():
    try:
        return find_kicad_cli()
    except PcbAiError:
        return None


def digests(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file()}


class PrivateConfigTests(unittest.TestCase):
    def test_copy_keeps_files_tables_and_themes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_cli = Path(tmp) / "KiCad/10.0/bin/kicad-cli.exe"
            user = Path(tmp) / "appdata/kicad/10.0"
            (user / "colors").mkdir(parents=True)
            (user / "kicad_common.json").write_text("{}")
            (user / "fp-lib-table").write_text("(fp_lib_table)")
            (user / "colors/mine.json").write_text("{}")
            (user / "3rdparty").mkdir()
            with patch.dict(os.environ, {"APPDATA": str(Path(tmp) / "appdata")}, clear=False):
                os.environ.pop("KICAD_CONFIG_HOME", None)
                home = private_kicad_config(fake_cli, Path(tmp) / "private")
            self.assertEqual(sorted(p.relative_to(home).as_posix() for p in home.rglob("*") if p.is_file()),
                             ["10.0/colors/mine.json", "10.0/fp-lib-table", "10.0/kicad_common.json"])


@unittest.skipUnless(cli(), "kicad-cli required")
class UserSettingsUntouchedTests(unittest.TestCase):
    def test_real_kicad_cli_never_writes_user_settings(self):
        """KiCad 10.0.4 rewrites system.working_dir on every run; PcbAi must run it against a private copy."""
        demo = Path(cli()).parent.parent / "share/kicad/demos/ecc83"
        with tempfile.TemporaryDirectory(prefix="pcbai-cfg-") as tmp:
            appdata = Path(tmp) / "appdata"
            user = appdata / "kicad" / Path(cli()).resolve().parents[1].name
            user.mkdir(parents=True)
            (user / "kicad_common.json").write_text('{"system": {"working_dir": "UNCHANGED"}}')
            project = Path(tmp) / "p"
            shutil.copytree(demo, project)
            before = digests(user)
            env = {"APPDATA": str(appdata)}
            with patch.dict(os.environ, env, clear=False):
                os.environ.pop("KICAD_CONFIG_HOME", None)
                process = run([cli(), "pcb", "drc", project / "ecc83-pp.kicad_pcb", "--output", project / "r.json"],
                              cwd=project)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(digests(user), before)
