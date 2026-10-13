import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from pcbai.core.contract import PcbAiError
from pcbai.pcb.engines import describe, execute


class EngineInventoryTests(unittest.TestCase):
    def test_partial_route_exit_three_is_measured_but_fatal_or_place_exit_is_rejected(self):
        for operation, code, accepted in [('route', 3, True), ('route', 1, False), ('place', 3, False), ('place', 1, False)]:
            with self.subTest(operation=operation, code=code), tempfile.TemporaryDirectory() as tmp:
                def build(_operation, source, dest, _options, _timeout, *, home=None):
                    return [sys.executable, str(source), str(dest)], True
                def child(argv, code=code, **kwargs):
                    Path(argv[-1]).write_bytes(Path(argv[-2]).read_bytes())
                    return dict(returncode=code, stderr_tail='protocol', stdout_tail='')
                with patch('pcbai.pcb.engines.tracemaker.build', side_effect=build), patch('pcbai.pcb.engines.run_process', side_effect=child), patch('pcbai.pcb.engines.describe', return_value=[dict(engine='tracemaker', version='0.9.0')]):
                    if accepted:
                        data, outcome = execute(Path(tmp), b'private fixture', 'tracemaker', operation, {})
                        self.assertEqual(data, b'private fixture')
                        self.assertEqual(outcome['returncode'], 3)
                        self.assertFalse(outcome['route_complete_reported'])
                    else:
                        with self.assertRaises(PcbAiError) as exc:
                            execute(Path(tmp), b'private fixture', 'tracemaker', operation, {})
                        self.assertEqual(exc.exception.code, 'engine_failed')

    def test_tracemaker_version_subcommand_and_lowercase_semver(self):
        calls = []
        def protocol(command, **options):
            calls.append(command)
            self.assertFalse("--version" in command, "Pinned TraceMaker CLI has no --version flag")
            self.assertEqual(command, [sys.executable, "version"])
            self.assertLessEqual(options["timeout"], 15)
            self.assertNotEqual(options["env"]["HOME"], "")
            return CompletedProcess(command, 0, "tracemaker 0.9.0\n", "")
        with patch("pcbai.pcb.engines.find_freerouting", side_effect=PcbAiError("missing_dependency", "not installed")), patch("pcbai.pcb.engines.find_tracemaker", return_value=sys.executable), patch("pcbai.pcb.engines.run", side_effect=protocol):
            inventory = describe()
        self.assertEqual(len(calls), 1)
        trace = inventory[1]
        self.assertTrue(trace["available"])
        self.assertEqual(trace["version"], "0.9.0")
        self.assertIsNone(trace["commit"])
        self.assertFalse(trace["tested"])

    def test_failed_version_query_remains_unavailable(self):
        with patch("pcbai.pcb.engines.find_freerouting", side_effect=PcbAiError("missing_dependency", "not installed")), patch("pcbai.pcb.engines.find_tracemaker", return_value=sys.executable), patch("pcbai.pcb.engines.run", return_value=CompletedProcess([], 2, "", "cannot execute")):
            trace = describe()[1]
        self.assertFalse(trace["available"])
        self.assertEqual(trace["code"], "engine_unavailable")
        self.assertFalse(trace["tested"])

    def test_wsl_version_query_keeps_isolated_timeout_arguments(self):
        observed = []
        def protocol(command, **options):
            observed.append(command)
            self.assertEqual(command[-2:], ["/opt/tracemaker", "version"])
            self.assertIn("timeout", command)
            self.assertIn("--kill-after=5", command)
            self.assertTrue(any(arg.startswith("HOME=/mnt/") for arg in command))
            return CompletedProcess(command, 0, "TraceMaker v0.9.0\n", "")
        with patch("pcbai.pcb.engines.find_freerouting", side_effect=PcbAiError("missing_dependency", "not installed")), patch("pcbai.pcb.engines.find_tracemaker", return_value="wsl:Ubuntu:/opt/tracemaker"), patch("pcbai.pcb.engines.wsl.shutil.which", return_value="wsl.exe"), patch("pcbai.pcb.engines.run", side_effect=protocol):
            trace = describe()[1]
        self.assertEqual(len(observed), 1)
        self.assertTrue(trace["available"])
        self.assertEqual(trace["via"], "wsl")
        self.assertEqual(trace["version"], "0.9.0")
