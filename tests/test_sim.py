import math
import shutil
import tempfile
import unittest
from bisect import bisect_left
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli
from pcbai.sim.runner import sanitize, simulate_lines, summarize
from pcbai.tools.engine import Engine


class SanitizeTests(unittest.TestCase):
    def test_nested_models_are_checked_and_inlined(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            model = root / "model with spaces.lib"
            model.write_text('.include "nested.lib"\n.control\nshell touch bad\n.endc\n', encoding="utf-8")
            nested = root / "nested.lib"
            nested.write_text('.model DSAFE D(Is=1n)\n', encoding="utf-8")
            text = f'Test\n.include "{model.as_posix()}"\n.op\n.end'
            lines, notes, _ = sanitize(text, [root])
            self.assertTrue(notes)
            self.assertIn('.model DSAFE D(Is=1n)', lines)
            self.assertFalse(any('.include' in s or 'shell' in s for s in lines))
            outside = Path(other) / "private.lib"
            outside.write_text("* private")
            for unsafe in (f'.include "{outside.as_posix()}"', '.include "nested.lib"', '.osdi "plugin.dll"',
                           '.model X filesource(file="C:/private.txt")', '.control\nshell bad',
                           '.model X d_source(input_file="C:/outside.txt")',
                           '.model X d_process(process="bad")', '.model X d_cosim',
                           '.model X D(output_file="C:/outside.txt")'):
                nested.write_text(unsafe, encoding="utf-8")
                with self.assertRaises(PcbAiError) as raised:
                    sanitize(text, [root])
                self.assertEqual(raised.exception.code, "unsafe_netlist")

    def test_model_library_section_and_tab_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "m.lib"
            model.write_text('.lib TT\n.model DSAFE D(Is=1n)\n.endl TT\n.lib FF\n.osdi bad\n.endl FF')
            lines, _, _ = sanitize(f'Test\n.lib "{model.as_posix()}" TT\n.op\n.end', [tmp])
            self.assertIn('.model DSAFE D(Is=1n)', lines)
            self.assertFalse(any('.lib' in line for line in lines))
            lines, notes, _ = sanitize('Test\n.control\tsomething\nshell bad\n.endc\n.op\n.end', [tmp])
            self.assertTrue(notes)
            self.assertNotIn('shell bad', lines)

    def test_control_blocks_dropped_and_single_analysis_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "m.lib"
            model.write_text("* model")
            text = (f'.title t\n.include "{model.as_posix()}"\n.tran 1u 1m\n.control\nshell del C:\\x\n'
                    "wrdata out.txt v(a)\n.endc\nR1 a 0 1k\n.end\n")
            lines, warnings, analyses = sanitize(text, [tmp])
            self.assertEqual(analyses, ["tran"])
            self.assertFalse(any("shell" in line or "wrdata" in line for line in lines))
            self.assertTrue(warnings)
            for bad in (text.replace(".tran 1u 1m\n", ""), text.replace(".tran 1u 1m\n", ".tran 1u 1m\n.ac dec 10 1 1k\n"),
                        text.replace(".endc\n", "")):
                with self.assertRaises(PcbAiError):
                    sanitize(bad, [tmp])

    def test_model_files_outside_allowed_roots_refused(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            outside = Path(other) / "secret.lib"
            outside.write_text("x")
            for line in (f'.include "{outside.as_posix()}"', ".include relative.lib", '.lib "/no/such/file.lib" X'):
                with self.assertRaises(PcbAiError) as raised:
                    sanitize(f".title t\n{line}\n.op\n.end\n", [tmp])
                self.assertEqual(raised.exception.code, "unsafe_netlist")


def kicad():
    try:
        cli = Path(find_kicad_cli())
    except PcbAiError:
        return None
    return cli.parent.parent if (cli.parent / "ngspice.dll").is_file() or (cli.parent / "libngspice.so").is_file() else None


@unittest.skipUnless(kicad(), "KiCad with shared ngspice required")
class NgspiceTests(unittest.TestCase):
    def test_rc_transient_within_one_percent_of_hand_calculation(self):
        """S5 acceptance: RC .tran within 1 % of 1 - exp(-t/RC) (tau = 1 ms)."""
        with tempfile.TemporaryDirectory() as tmp:
            output = simulate_lines(["RC", "V1 in 0 PULSE(0 1 0 1n 1n 10m 20m)", "R1 in out 1k", "C1 out 0 1u",
                                     ".tran 1u 5m", ".end"], tmp, ["time", "v(out)"], max_points=20000)
        t, v = output["vectors"]["time"]["values"], output["vectors"]["v(out)"]["values"]
        for target in (0.25e-3, 0.5e-3, 1e-3, 2e-3, 4e-3):
            i = bisect_left(t, target)
            y = v[i - 1] + (v[i] - v[i - 1]) * (target - t[i - 1]) / (t[i] - t[i - 1])
            exact = 1 - math.exp(-target / 1e-3)
            self.assertLess(abs(y - exact) / exact, 0.01)
        self.assertEqual(summarize(output["vectors"])["v(out)"]["nonfinite"], 0)

    def test_sallen_key_schematic_gain_at_corner_frequency(self):
        """Real KiCad schematic + op-amp model: equal-R/C unity-gain Sallen-Key has |H(1/2πRC)| = Q = 0.5."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sk"
            shutil.copytree(kicad() / "share/kicad/demos/simulation/sallen_key", root)
            state = Path(tmp) / "state"
            state.mkdir()
            engine = Engine([root / "sallen_key.kicad_pro"], state)
            session = next(iter(engine.sessions.entries.values()))
            original = (root / "sallen_key.kicad_sch").read_bytes()
            response = engine.call("simulate", dict(session.target("sallen_key.kicad_sch"),
                                                    vectors=["frequency", "/lowpass"], max_points=20000))
            self.assertTrue(response["ok"], response)
            self.assertEqual(response["analysis"], "ac")
            self.assertTrue(any(".control" in w for w in response["warnings"]))
            self.assertTrue(response["evidence_id"].startswith("ev-"))
            frequency = response["vectors"]["frequency"]["values"]
            frequency = frequency["real"] if isinstance(frequency, dict) else frequency
            out = response["vectors"]["/lowpass"]["values"]
            magnitude = [math.hypot(a, b) for a, b in zip(out["real"], out["imag"], strict=True)]
            f0 = 1 / (2 * math.pi * 1e3 * 100e-9)
            a = max(k for k in range(len(frequency)) if frequency[k] <= f0)
            w = (math.log(f0) - math.log(frequency[a])) / (math.log(frequency[a + 1]) - math.log(frequency[a]))
            gain = magnitude[a] + (magnitude[a + 1] - magnitude[a]) * w
            self.assertLess(abs(gain - 0.5) / 0.5, 0.01)
            self.assertLess(abs(magnitude[0] - 1), 0.01)
            self.assertEqual((root / "sallen_key.kicad_sch").read_bytes(), original)
            missing = engine.call("simulate", session.target("sallen_key.kicad_sch") | {"document": "nope.kicad_sch"})
            self.assertFalse(missing["ok"])
