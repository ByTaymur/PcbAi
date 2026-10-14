"""Ideal passive recipe testbenches; user text never becomes a SPICE statement."""
import hashlib
import math
from bisect import bisect_left

from pcbai.blocks.registry import expand
from pcbai.core.contract import PcbAiError
from pcbai.sim.runner import sanitize, simulate_lines
from pcbai.sim.coverage import coverage, meets_threshold


def bench(block, params):
    recipe = expand(block, params)
    pins = recipe['port_pins']
    nodes = {}
    # Alias ports share physical pins. Resolve from those pins rather than reimplementing recipes.
    for port in ('GND', 'OUT', 'INPUT', 'IN', 'SUPPLY'):
        members = pins.get(port, [])
        if not members:
            continue
        existing = {nodes[(p['part'], p['pin'])] for p in members if (p['part'], p['pin']) in nodes}
        if len(existing) > 1:
            raise PcbAiError('invalid_block_topology', 'Recipe joins distinct testbench nodes')
        node = next(iter(existing), {'GND': '0', 'OUT': 'out', 'INPUT': 'out', 'IN': 'src', 'SUPPLY': 'src'}[port])
        for p in members:
            nodes[(p['part'], p['pin'])] = node
    lines = ['PcbAi ideal passive recipe test']
    for part in recipe['parts']:
        value = part['value_si']
        low, high = (1e-3, 1e12) if part['symbol'] == 'Device:R' else (1e-15, 1)
        if not low <= value <= high:
            raise PcbAiError('unsupported_simulation_range', 'Passive value is outside the bounded ideal test range')
        lines.append(f"{part['id']} {nodes[(part['id'], '1')]} {nodes[(part['id'], '2')]} {value:.17g}")
    calc = recipe['calculation']
    if block == 'voltage_divider':
        vin = calc['normalized_inputs']['vin']
        if abs(vin) > 1e6:
            raise PcbAiError('unsupported_simulation_range', 'Source magnitude exceeds 1 MV')
        lines.extend([f'Vdrive src 0 {vin:.17g}', '.op'])
        vectors = ['v(out)', 'i(vdrive)']
    else:
        tau = calc['outputs']['tau']
        if not 1e-12 <= tau <= 1e6:
            raise PcbAiError('unsupported_simulation_range', 'RC time constant is outside the bounded ideal test range')
        if block == 'rc_filter':
            fc = calc['outputs']['cutoff']
            lines.extend(['Vdrive src 0 AC 1', f'.ac lin 1 {fc:.17g} {fc:.17g}'])
            vectors = ['frequency', 'v(out)']
        else:
            if params['direction'] == 'pullup':
                lines.append(f'Vdrive src 0 PULSE(0 1 0 {tau * 1e-6:.17g} {tau * 1e-6:.17g} {tau * 10:.17g} {tau * 20:.17g})')
            else:
                lines.append('.ic v(out)=1')
            lines.append(f'.tran {tau / 1000:.17g} {tau * 5:.17g}' + (' uic' if params['direction'] == 'pulldown' else ''))
            vectors = ['time', 'v(out)']
    lines.append('.end')
    clean, notes, _ = sanitize('\n'.join(lines), [])
    assert not notes
    return recipe, clean, vectors


def real_values(output, name, complex_scale=False):
    try:
        values = output['vectors'][name]['values']
        # ngspice AC scales may carry the complex flag with exactly zero imaginary part.
        if complex_scale and isinstance(values, dict):
            real, imag = values['real'], values['imag']
            if len(real) != len(imag) or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v != 0 for v in imag):
                raise ValueError('non-real scale')
            values = real
        if not isinstance(values, list) or not values or any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in values):
            raise ValueError('non-finite or non-real vector')
        return values
    except (KeyError, TypeError, ValueError) as exc:
        raise PcbAiError('simulation_failed', f'Missing/invalid simulation vector: {name}') from exc


def measure(block, params, recipe, output):
    checks = []
    def check(name, measured, expected, unit, absolute=1e-9):
        if not math.isfinite(measured):
            raise PcbAiError('simulation_failed', 'Non-finite simulation measurement')
        tolerance = max(abs(expected) * .01, absolute)
        checks.append(dict(name=name, measured=measured, expected=expected, unit=unit,
                           absolute_error=abs(measured - expected), tolerance=tolerance,
                           passed=abs(measured - expected) <= tolerance))
    calc = recipe['calculation']
    if block == 'voltage_divider':
        check('vout', real_values(output, 'v(out)')[-1], calc['outputs']['vout'], 'V')
        check('input_current', -real_values(output, 'i(vdrive)')[-1], calc['outputs']['input_current'], 'A', 1e-15)
    elif block == 'rc_filter':
        frequency = real_values(output, 'frequency', complex_scale=True)
        try:
            values = output['vectors']['v(out)']['values']
            real, imag = values['real'], values['imag']
            if len(real) != 1 or len(imag) != 1 or any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in (real[0], imag[0])):
                raise ValueError('invalid AC vector')
        except (KeyError, TypeError, ValueError) as exc:
            raise PcbAiError('simulation_failed', 'Missing/invalid complex output vector') from exc
        if len(frequency) != 1:
            raise PcbAiError('simulation_failed', 'Expected one AC sample at the corner frequency')
        check('frequency', frequency[0], calc['outputs']['cutoff'], 'Hz', 1e-15)
        check('corner_magnitude', math.hypot(real[0], imag[0]), 1 / math.sqrt(2), 'ratio')
        check('corner_phase', math.atan2(imag[0], real[0]), math.pi / 4 if params.get('type') == 'highpass' else -math.pi / 4, 'rad')
    else:
        times, values = real_values(output, 'time'), real_values(output, 'v(out)')
        if len(times) != len(values) or any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise PcbAiError('simulation_failed', 'Time samples must be aligned and strictly increasing')
        tau = calc['outputs']['tau']
        for multiple in (.25, .5, 1, 2, 4):
            target = multiple * tau
            index = bisect_left(times, target)
            if index == 0 or index == len(times):
                raise PcbAiError('simulation_failed', 'Transient samples do not cover the comparison interval')
            v = values[index - 1] + (values[index] - values[index - 1]) * (target - times[index - 1]) / (times[index] - times[index - 1])
            decay = math.exp(-multiple)
            check(f'vout_at_{multiple:g}tau', v, decay if params['direction'] == 'pulldown' else 1 - decay, 'V')
    return checks


def test_block(block, params, cwd, *, min_coverage=None):
    recipe, lines, vectors = bench(block, params)
    models = coverage([dict(reference=p["id"], active=False, connected=True, lib_id=p["symbol"])
                       for p in recipe["parts"]], lines)
    if not meets_threshold(models, min_coverage):
        return dict(block=block, coverage=models, verification="checks_incomplete", checks=[],
                    passed=False, original_inputs=params, min_coverage=min_coverage)
    output = simulate_lines(lines, cwd, vectors, max_points=20000, timeout=60)
    checks = measure(block, params, recipe, output)
    passed = all(c['passed'] for c in checks)
    return dict(block=block, recipe_version=recipe['version'], testbench_version=1, maturity=0,
                verification='simulated' if passed else 'simulation_mismatch', passed=passed,
                checks=checks, calculation=recipe['calculation'], parts=recipe['parts'],
                netlist=lines, netlist_sha256=hashlib.sha256('\n'.join(lines).encode()).hexdigest(), coverage=models,
                simulator_plot=output['plot'], erc_verified=False, stock_verified=False, physically_verified=False,
                assumptions=['Ideal R/C and ideal source; no tolerance, parasitics or source impedance',
                             'Generated recipe topology; no user schematic or installed part model tested'],
                warnings=recipe['warnings'])
