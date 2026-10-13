import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pcbai.config import state_directory, validate_state_location
from pcbai.core.contract import PcbAiError
from pcbai.service.server import serve
from pcbai.tools.engine import Engine
from tests.helpers import make_project


class StateLocationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pcbai-state-boundary-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = make_project(self.root / "project")

    def reject(self, operation):
        with self.assertRaises(PcbAiError) as raised:
            operation()
        self.assertEqual(raised.exception.code, "invalid_state_directory")

    def test_nested_equal_and_ancestor_state_rejected_before_engine_writes(self):
        original = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        nested = self.project.parent / "new-state"
        for state in (nested, self.project.parent, self.root, nested / ".."):
            self.reject(lambda state=state: Engine([self.project], state))
        self.assertFalse(nested.exists())
        current = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(current, original)

    def test_config_refuses_overlap_before_private_directory_acl_or_marker(self):
        nested = self.project.parent / "state"
        with patch.dict(os.environ, PCBAI_STATE_DIR=str(nested)), patch("pcbai.config.private_directory", side_effect=AssertionError("state mutated")):
            self.reject(lambda: state_directory([self.project.parent]))
        self.assertFalse(nested.exists())
        with patch.dict(os.environ, PCBAI_STATE_DIR=str(self.root)), patch("pcbai.config.private_directory", side_effect=AssertionError("project ACL narrowed")):
            self.reject(lambda: state_directory([self.project.parent]))

    def test_service_and_inspect_entrypoints_reject_before_state_preparation(self):
        nested = self.project.parent / "state"
        with patch.dict(os.environ, PCBAI_STATE_DIR=str(nested)), patch("pcbai.config.private_directory", side_effect=AssertionError("state prepared")):
            self.reject(lambda: serve([self.project]))
            from pcbai.__main__ import main
            with patch("sys.argv", ["pcbai", "inspect", str(self.project)]):
                self.reject(main)
        self.assertFalse(nested.exists())

    def test_sibling_prefix_canonical_dot_paths_multi_projects_and_global_tools(self):
        external = self.root / "project-state"
        external.mkdir()
        self.assertEqual(validate_state_location(external, [self.project.parent]), external.resolve())
        engine = Engine([self.project], self.project.parent / ".." / "project-state")
        self.assertEqual(engine.state, external.resolve())
        self.assertTrue(engine.call("pcbai_status", {})["ok"])
        global_engine = Engine([], external)
        self.assertTrue(global_engine.call("hand_calc", dict(calculation="rc_filter", params=dict(r="1k", c="1uF")))["ok"])
        second = make_project(self.root / "other")
        self.reject(lambda: Engine([self.project, second], second.parent / "state"))
        if os.name == "nt":
            self.reject(lambda: validate_state_location(Path(str(self.project.parent).upper()) / "state", [self.project.parent]))

    def test_service_preserves_one_shot_projects_generator(self):
        state = self.root / "external"
        state.mkdir()
        received = []
        class StopProbe(Exception):
            pass
        def observe(projects, directory):
            received.extend(projects)
            raise StopProbe()
        with patch.dict(os.environ, PCBAI_STATE_DIR=str(state)), patch("pcbai.service.server.Engine", side_effect=observe):
            with self.assertRaises(StopProbe):
                serve(p for p in [self.project])
        self.assertEqual(received, [self.project])
        self.assertFalse((state / "service.json").exists())

    def test_home_shorthand_validates_and_prepares_the_same_path(self):
        external = self.root / "external"
        shorthand = Path("~/state")
        def expand(path):
            return external if path == shorthand else path
        with patch.dict(os.environ, PCBAI_STATE_DIR=str(shorthand)), patch("pathlib.Path.expanduser", autospec=True, side_effect=expand), patch("pcbai.config.private_directory", return_value=external) as prepare:
            self.assertEqual(state_directory([self.project.parent]), external)
            prepare.assert_called_once_with(external)
