"""Dimension-aware SI parsing. Text is never a Python/SPICE expression."""
import math
import re

from pcbai.core.contract import PcbAiError

UNITS = {"resistance": "Ω", "capacitance": "F", "inductance": "H", "voltage": "V", "current": "A",
         "time": "s", "frequency": "Hz", "power": "W", "length": "m"}
ALIASES = {"Ω": "resistance", "Ω": "resistance", "ohm": "resistance", "Ohm": "resistance",
           **{unit: kind for kind, unit in UNITS.items()}}
PREFIXES = {"": 1, "f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6,
            "m": 1e-3, "k": 1e3, "M": 1e6, "G": 1e9, "T": 1e12}
NUM = r"[+-]?(?:\d{1,24}(?:\.\d{0,24})?|\.\d{1,24})(?:[eE][+-]?\d{1,2})?"
SCALAR = re.compile(r"(" + NUM + r")\s*([fpnumkMGTµμ]?)(Ω|Ω|ohm|Ohm|F|H|V|A|s|Hz|W|m)?")
RESISTOR = re.compile(r"(\d{1,12})([RrkmM])(\d{1,12})")
RANGE = re.compile(r"(" + NUM + r")\s*(?:-|\.\.|…)\s*(" + NUM + r")\s*([^\d\s].*)")


def quantity(value, dimension):
    if not isinstance(dimension, str) or dimension not in UNITS:
        raise PcbAiError("invalid_quantity", "Unknown quantity dimension")
    if isinstance(value, bool):
        raise PcbAiError("invalid_quantity", "Booleans are not electrical quantities")
    if isinstance(value, (int, float)):
        try:
            result = float(value)
        except OverflowError as exc:
            raise PcbAiError("invalid_quantity", "Quantity overflowed") from exc
    elif isinstance(value, str) and len(value) <= 80:
        raw = value.strip()
        shorthand = RESISTOR.fullmatch(raw) if dimension == "resistance" else None
        if shorthand:
            a, mark, b = shorthand.groups()
            result = float(a + "." + b) * ({"R": 1, "r": 1}.get(mark, PREFIXES.get(mark)))
        else:
            match = SCALAR.fullmatch(raw)
            if not match:
                raise PcbAiError("invalid_quantity", f"Expected a {dimension} number or SI quantity, not an expression")
            number, prefix, unit = match.groups()
            if unit is None and prefix == "m" and (dimension == "length" or raw[match.end(1):match.start(2)].strip() != raw[match.end(1):match.start(2)]):
                prefix, unit = "", "m"
            if unit is not None and ALIASES[unit] != dimension:
                raise PcbAiError("dimension_mismatch", f"Expected {UNITS[dimension]}, received {unit}")
            result = float(number) * PREFIXES[prefix]
    else:
        raise PcbAiError("invalid_quantity", "Quantity must be a finite number or bounded SI text")
    if not math.isfinite(result) or (result and not 1e-24 <= abs(result) <= 1e30):
        raise PcbAiError("invalid_quantity", "Quantity is nonfinite or outside supported magnitude limits")
    return result


def positive(value, dimension):
    result = quantity(value, dimension)
    if result <= 0:
        raise PcbAiError("invalid_quantity", dimension + " must be positive")
    return result


def quantity_range(value, dimension):
    if isinstance(value, dict) and set(value) == {"min", "max"}:
        lower, upper = quantity(value["min"], dimension), quantity(value["max"], dimension)
    elif isinstance(value, str) and len(value) <= 100 and (match := RANGE.fullmatch(value.strip())):
        lower, upper, suffix = match.groups()
        lower, upper = quantity(lower + suffix, dimension), quantity(upper + suffix, dimension)
    else:
        lower = upper = quantity(value, dimension)
    if lower > upper:
        raise PcbAiError("invalid_quantity", "Range minimum exceeds maximum")
    return dict(min=lower, max=upper, unit=UNITS[dimension])
