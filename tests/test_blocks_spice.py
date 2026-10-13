import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pcbai.blocks.spice import bench, measure, test_block
from pcbai.core.contract import PcbAiError
from pcbai.tools.engine import Engine
from tests.test_sim import kicad


CASES = [
    ('voltage_divider', dict(vin='5V', r_top='10k', r_bottom='10k')),
    ('voltage_divider', dict(vin='-5V', r_top='10k', r_bottom='20k', r_load='10k')),
    ('rc_filter', dict(r='10k', c='100nF', type='lowpass')),
    ('rc_filter', dict(r='10k', c='100nF', type='highpass')),
    ('button_debounce', dict(r='10k', c='100nF', direction='pullup')),
    ('button_debounce', dict(r='10k', c='100nF', direction='pulldown')),
]


class PassiveBenchTests(unittest.TestCase):
    def test_generated_topology_uses_recipe_pins_and_aliases(self):
        expected = [
            ['R1 src out 10000', 'R2 out 0 10000'],
            ['R1 src out 10000', 'R2 out 0 20000', 'RL out 0 10000'],
            ['R1 src out 10000', 'C1 out 0 9.9999999999999995e-08'],
            ['R1 out 0 10000', 'C1 src out 9.9999999999999995e-08'],
            ['R1 src out 10000', 'C1 out 0 9.9999999999999995e-08'],
            ['R1 0 out 10000', 'C1 out 0 9.9999999999999995e-08'],
        ]
        for (block, params), parts in zip(CASES, expected, strict=True):
            with self.subTest(block=block, params=params):
                _, lines, _ = bench(block, params)
                actual = [s.split() for s in lines if s.startswith(('R', 'C'))]
                self.assertEqual([s[:3] for s in actual], [s.split()[:3] for s in parts])
                for got, want in zip(actual, parts, strict=True):
                    self.assertAlmostEqual(float(got[3]) / float(want.split()[3]), 1.0)
                self.assertFalse(any(s.startswith(('.include', '.control', '.model')) for s in lines))

    def test_injection_unknown_params_and_ranges_rejected_before_worker(self):
        bad = [dict(r='10k\n.include private', c='100nF'), dict(r='10k', c='100nF', file='secret'),
               dict(r=True, c='100nF'), dict(r='1e-4', c='100nF'), dict(r='1e12', c='1')]
        with tempfile.TemporaryDirectory() as tmp, patch('pcbai.blocks.spice.simulate_lines') as worker:
            for params in bad:
                with self.subTest(params=params), self.assertRaises(PcbAiError):
                    test_block('rc_filter', params, tmp)
            worker.assert_not_called()

    def test_wrong_valid_result_is_mismatch_and_missing_vector_fails(self):
        block, params = CASES[0]
        recipe, _, _ = bench(block, params)
        data = dict(plot='op1', vectors={'v(out)': dict(values=[4.0]), 'i(vdrive)': dict(values=[-.00025])})
        with tempfile.TemporaryDirectory() as tmp, patch('pcbai.blocks.spice.simulate_lines', return_value=data):
            report = test_block(block, params, tmp)
        self.assertFalse(report['passed'])
        self.assertEqual(report['verification'], 'simulation_mismatch')
        for values in ([None], [float('nan')], [], [True]):
            data['vectors']['v(out)']['values'] = values
            with self.assertRaises(PcbAiError):
                measure(block, params, recipe, data)

    def test_transient_requires_full_monotone_aligned_samples(self):
        block, params = CASES[4]
        recipe, _, _ = bench(block, params)
        for times, values in [([0, .0001], [0, .1]), ([0, .005, .004], [0, .99, .98]), ([0, .005], [0])]:
            data = dict(vectors={'time': dict(values=times), 'v(out)': dict(values=values)})
            with self.assertRaises(PcbAiError):
                measure(block, params, recipe, data)

    def test_ac_scale_requires_numeric_finite_zero_imaginary_part(self):
        block, params = CASES[2]
        recipe, _, _ = bench(block, params)
        for value in (False, None, float('nan'), .1):
            data = dict(vectors={'frequency': dict(values=dict(real=[recipe['calculation']['outputs']['cutoff']], imag=[value])),
                                 'v(out)': dict(values=dict(real=[.5], imag=[-.5]))})
            with self.subTest(value=value), self.assertRaises(PcbAiError):
                measure(block, params, recipe, data)


@unittest.skipUnless(kicad(), 'KiCad with shared ngspice required')
class PassiveSpiceTests(unittest.TestCase):
    def test_all_six_variants_real_ngspice_within_one_percent(self):
        with tempfile.TemporaryDirectory() as tmp:
            for block, params in CASES:
                with self.subTest(block=block, params=params):
                    report = test_block(block, params, tmp)
                    self.assertTrue(report['passed'], report['checks'])
                    self.assertTrue(all(c['passed'] for c in report['checks']))
                    self.assertEqual(report['maturity'], 0)
                    self.assertFalse(report['erc_verified'])
                    self.assertFalse(report['physically_verified'])

    def test_global_engine_records_simulated_provenance_without_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = Engine([], Path(tmp))
            definition = next(d for d in engine.definitions if d['name'] == 'spice_block_test')
            self.assertTrue(definition['annotations']['readOnlyHint'])
            block, params = CASES[0]
            arguments = dict(block=block, params=params)
            response = engine.call('spice_block_test', arguments)
            self.assertTrue(response['ok'], response)
            self.assertTrue(response['passed'])
            self.assertEqual(response['verified'], 'simulated')
            self.assertTrue(response['measurements'])
            self.assertEqual(response['original_inputs'], arguments)
            entry = json.loads((engine.evidence.root / (response['evidence_id'] + '.json')).read_text())
            self.assertIsNone(entry['target'])
            self.assertTrue(all(m['source'] == 'simulated' for m in entry['measurements']))
            self.assertEqual(list(engine.exports.iterdir()), [])
            bad = engine.call('spice_block_test', dict(block='rc_filter', params=dict(r='x', c='100nF')))
            self.assertFalse(bad['ok'])
            self.assertEqual(len(list(engine.evidence.root.iterdir())), 1)
