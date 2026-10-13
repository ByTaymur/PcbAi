"""Reproducible hand calculations shared by block expansion and tool results."""
import math

from pcbai.core.contract import PcbAiError
from pcbai.ir.units import UNITS, positive, quantity

E12 = (1, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2)
E24 = (1, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2, 2.2, 2.4, 2.7, 3, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1)


def nearest(value, series="E24"):
    if not isinstance(series, str) or series not in {"E12", "E24"} or not math.isfinite(value) or value <= 0:
        raise PcbAiError("invalid_calculation", "Use a positive value and E12 or E24 series")
    decade = math.floor(math.log10(value))
    candidates = [n * 10 ** (decade + offset) for offset in (-1, 0, 1) for n in (E12 if series == "E12" else E24)]
    return min(candidates, key=lambda n: (abs(n - value), n))


def parameters(values, required, optional=()):
    if not isinstance(values, dict) or set(values) - set(required) - set(optional) or set(required) - set(values):
        raise PcbAiError("invalid_calculation", "Required: " + ", ".join(required) + "; optional: " + ", ".join(optional))


def report(kind, normalized, outputs, units, formula, assumptions=(), warnings=()):
    if any(not math.isfinite(v) for v in outputs.values()):
        raise PcbAiError("invalid_calculation", "Calculation overflowed")
    return dict(calculation=kind, formula_version=1, normalized_inputs=normalized, outputs=outputs,
                output_units=units, formula=formula, assumptions=list(assumptions), warnings=list(warnings),
                verification="calculated", physically_verified=False)


def calculate(kind, p):
    if kind == "divider":
        parameters(p, ("vin", "r_top", "r_bottom"), ("r_load",))
        vin, top, bottom = quantity(p["vin"], "voltage"), positive(p["r_top"], "resistance"), positive(p["r_bottom"], "resistance")
        effective = bottom
        normalized = dict(vin=vin, r_top=top, r_bottom=bottom)
        if "r_load" in p:
            load = positive(p["r_load"], "resistance")
            effective = 1 / (1 / bottom + 1 / load)
            normalized["r_load"] = load
        current = vin / (top + effective)
        out = current * effective
        outputs = dict(ratio=effective / (top + effective), unloaded_ratio=bottom / (top + bottom),
                       vout=out, input_current=current, top_power=current ** 2 * top, bottom_power=out ** 2 / bottom,
                       output_resistance=1 / (1 / top + 1 / bottom))
        if "r_load" in normalized:
            outputs["load_power"] = out ** 2 / normalized["r_load"]
        return report(kind, normalized, outputs,
            dict(ratio="ratio", unloaded_ratio="ratio", vout="V", input_current="A", top_power="W", bottom_power="W",
                 output_resistance="Ω", **({"load_power": "W"} if "r_load" in normalized else {})),
            "Rlower = Rbottom || Rload; Vout = Vin * Rlower / (Rtop + Rlower)", ["Ideal resistors; source impedance excluded"])
    if kind in {"rc_filter", "button_debounce"}:
        parameters(p, ("r", "c"), ("settling_percent",))
        r, c = positive(p["r"], "resistance"), positive(p["c"], "capacitance")
        percent = p.get("settling_percent", 99)
        if isinstance(percent, bool) or not isinstance(percent, (int, float)) or not 0 < percent < 100:
            raise PcbAiError("invalid_calculation", "Settling percentage must be between 0 and 100")
        tau = r * c
        return report(kind, dict(r=r, c=c, settling_percent=percent),
            dict(tau=tau, cutoff=1 / (2 * math.pi * tau), settling_time=-tau * math.log1p(-percent / 100),
                 percent_at_5tau=100 * (1 - math.exp(-5))),
            dict(tau="s", cutoff="Hz", settling_time="s", percent_at_5tau="%"),
            "tau = R*C; fc = 1/(2*pi*R*C); t = -tau*ln(1-p/100)", ["Ideal unloaded RC"],
            ["An ideal RC response does not verify mechanical switch bounce"] if kind == "button_debounce" else [])
    if kind == "led_resistor":
        parameters(p, ("vin", "vf", "current"), ("series",))
        vin, vf, current = quantity(p["vin"], "voltage"), quantity(p["vf"], "voltage"), positive(p["current"], "current")
        if not 0 <= vf < vin:
            raise PcbAiError("invalid_calculation", "LED voltage must satisfy 0 <= Vf < Vin")
        exact = (vin - vf) / current
        recommended = nearest(exact, p.get("series", "E24"))
        actual = (vin - vf) / recommended
        return report(kind, dict(vin=vin, vf=vf, current=current),
            dict(target_resistance=exact, recommended_resistance=recommended, achieved_current=actual,
                 current_error_percent=100 * (actual / current - 1), resistor_power=actual ** 2 * recommended),
            dict(target_resistance="Ω", recommended_resistance="Ω", achieved_current="A", current_error_percent="%", resistor_power="W"),
            "R = (Vin - Vf)/I; Iachieved = (Vin - Vf)/Rpreferred", ["Caller-supplied constant forward voltage"],
            ["LED model, temperature and rating margins have not been verified"])
    if kind == "ldo_loss":
        parameters(p, ("vin", "vout", "current"), ("ambient_c", "theta_c_per_w"))
        vin, vout, current = positive(p["vin"], "voltage"), positive(p["vout"], "voltage"), positive(p["current"], "current")
        if vout > vin:
            raise PcbAiError("invalid_calculation", "LDO output voltage cannot exceed input")
        loss = (vin - vout) * current
        normalized, outputs, units = dict(vin=vin, vout=vout, current=current), dict(loss=loss), dict(loss="W")
        if "ambient_c" in p or "theta_c_per_w" in p:
            if not {"ambient_c", "theta_c_per_w"} <= set(p):
                raise PcbAiError("invalid_calculation", "Junction estimate needs ambient_c and theta_c_per_w")
            ambient, theta = p["ambient_c"], p["theta_c_per_w"]
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (ambient, theta)) or not -273.15 <= ambient <= 1000 or theta <= 0:
                raise PcbAiError("invalid_calculation", "Invalid caller-supplied thermal assumptions")
            normalized.update(ambient_c=ambient, theta_c_per_w=theta)
            outputs["junction_estimate"] = ambient + loss * theta
            units["junction_estimate"] = "°C"
        return report(kind, normalized, outputs, units, "Pd = (Vin - Vout)*I; Tj_est = Ta + Pd*theta",
            ["Quiescent current excluded", "Thermal resistance is caller-supplied, not a board measurement"],
            ["Dropout, datasheet limits, thermal layout and stock have not been verified"])
    if kind == "opamp_gain":
        parameters(p, ("r_feedback", "r_ground"), ("gbw",))
        rf, rg = positive(p["r_feedback"], "resistance"), positive(p["r_ground"], "resistance")
        gain = 1 + rf / rg
        normalized, outputs, units = dict(r_feedback=rf, r_ground=rg), dict(gain=gain), dict(gain="ratio")
        if "gbw" in p:
            normalized["gbw"] = positive(p["gbw"], "frequency")
            outputs["bandwidth_estimate"] = normalized["gbw"] / gain
            units["bandwidth_estimate"] = "Hz"
        return report(kind, normalized, outputs, units, "G = 1 + Rf/Rg; BW_est = GBW/G",
            ["Non-inverting topology; ideal/single-pole model"], ["Op-amp operating range and stability not verified"])
    if kind == "crystal_load":
        parameters(p, ("load", "stray"))
        load, stray = positive(p["load"], "capacitance"), quantity(p["stray"], "capacitance")
        if not 0 <= stray < load:
            raise PcbAiError("invalid_calculation", "Use 0 <= stray < specified crystal load")
        return report(kind, dict(load=load, stray=stray), dict(c_each=2 * (load - stray)), dict(c_each="F"),
            "C1 = C2 = 2*(CL - Cstray)", ["Equal external capacitors; caller-supplied stray estimate"],
            ["Oscillator startup, drive level and MCU configuration have not been verified"])
    if kind == "e_series":
        parameters(p, ("value", "dimension"), ("series",))
        value = positive(p["value"], p["dimension"])
        result = nearest(value, p.get("series", "E24"))
        return report(kind, dict(value=value, dimension=p["dimension"]),
            dict(recommended=result, error_percent=100 * (result / value - 1)),
            dict(recommended=UNITS[p["dimension"]], error_percent="%"), "Nearest nominal E12/E24 value; lower tie wins")
    raise PcbAiError("unknown_calculation", "Supported calculations: " + ", ".join(CALCULATIONS))


CALCULATIONS = ("divider", "rc_filter", "button_debounce", "led_resistor", "ldo_loss", "opamp_gain", "crystal_load", "e_series")
