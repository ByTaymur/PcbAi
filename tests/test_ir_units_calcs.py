import math
import unittest

from pcbai.core.contract import PcbAiError
from pcbai.ir.units import quantity, quantity_range
from pcbai.blocks.compute import calculate, nearest


class UnitTests(unittest.TestCase):
    def test_explicit_dimensions_and_scales(self):
        for text, dim, expected in (("1kΩ", "resistance", 1000), ("4k7", "resistance", 4700),
            ("100 nF", "capacitance", 1e-7), ("300 mA", "current", .3), ("1 MHz", "frequency", 1e6),
            ("1 mΩ", "resistance", .001), ("1 MΩ", "resistance", 1e6), ("1 μF", "capacitance", 1e-6),
            ("1 m", "length", 1), ("1mm", "length", .001), ("1m", "length", 1), ("1ms", "time", .001)):
            with self.subTest(text=text):
                self.assertAlmostEqual(quantity(text, dim), expected)
        self.assertEqual(quantity_range("9-24 V", "voltage"), dict(min=9, max=24, unit="V"))
        self.assertEqual(quantity_range({"min": "1kΩ", "max": "2kΩ"}, "resistance")["max"], 2000)

    def test_mismatch_expression_boolean_range_and_overflow_rejected(self):
        for value in (True, float("inf"), float("nan"), "1e309 V", "1e-99 V", "1k + 2k",
                      "__import__('os').system('bad')", "1; shell", "1 m", "1 Hz", 10**400):
            with self.subTest(value=str(value)[:60]), self.assertRaises(PcbAiError):
                quantity(value, "voltage")
        with self.assertRaises(PcbAiError):
            quantity_range("24-9 V", "voltage")


class CalculationTests(unittest.TestCase):
    def test_loaded_divider_kcl_and_energy_balance(self):
        result = calculate("divider", dict(vin="12 V", r_top="10kΩ", r_bottom="10kΩ", r_load="10kΩ"))
        out = result["outputs"]
        self.assertAlmostEqual(out["vout"], 4)
        self.assertAlmostEqual(out["unloaded_ratio"], .5)
        self.assertAlmostEqual(out["input_current"], out["vout"]/10000 * 2)
        self.assertAlmostEqual(12*out["input_current"], out["top_power"] + out["bottom_power"] + out["load_power"])
        self.assertFalse(result["physically_verified"])

    def test_rc_settling_and_led_preferred_value_achieved_current(self):
        result = calculate("rc_filter", dict(r="1kΩ", c="1uF"))["outputs"]
        self.assertAlmostEqual(result["tau"], .001)
        self.assertAlmostEqual(result["cutoff"], 1/(2*math.pi*.001))
        self.assertAlmostEqual(1-math.exp(-result["settling_time"]/result["tau"]), .99)
        led = calculate("led_resistor", dict(vin="5 V", vf="2 V", current="10 mA"))["outputs"]
        self.assertEqual(led["recommended_resistance"], 300)
        self.assertAlmostEqual(led["achieved_current"], .01)
        self.assertAlmostEqual(led["resistor_power"], .03)
        self.assertEqual(nearest(10000), 10000)

    def test_ldo_assumptions_and_remaining_formulas(self):
        result = calculate("ldo_loss", dict(vin=5, vout=3.3, current=.3, ambient_c=25, theta_c_per_w=50))["outputs"]
        self.assertAlmostEqual(result["loss"], .51)
        self.assertAlmostEqual(result["junction_estimate"], 50.5)
        self.assertNotIn("junction_estimate", calculate("ldo_loss", dict(vin=5,vout=3.3,current=.3))["outputs"])
        self.assertEqual(calculate("opamp_gain", dict(r_feedback="9kΩ", r_ground="1kΩ", gbw="1MHz"))["outputs"]["gain"], 10)
        self.assertAlmostEqual(calculate("crystal_load", dict(load="12pF", stray="3pF"))["outputs"]["c_each"], 18e-12)

    def test_invalid_domains_and_unknown_parameters_fail(self):
        for name, params in (("rc_filter", dict(r=0,c=1)), ("rc_filter",dict(r=1,c=1,settling_percent=100)),
                            ("led_resistor",dict(vin=2,vf=5,current=.01)), ("ldo_loss",dict(vin=3,vout=5,current=.1)),
                            ("ldo_loss",dict(vin=5,vout=3,current=.1,ambient_c=25)),
                            ("crystal_load",dict(load=1,stray=2)), ("divider",dict(vin=5,r_top=1,r_bottom=1,script="bad"))):
            with self.subTest(name=name), self.assertRaises(PcbAiError):
                calculate(name, params)
