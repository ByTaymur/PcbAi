"""Bounded, exact passive value parsing. Ambiguous notation stays unknown."""

import re
from decimal import Decimal, InvalidOperation, localcontext


def number(text):
    if not isinstance(text, str) or len(text) > 128:
        return None
    if not re.fullmatch(r"\d+(?:\.\d+)?(?:[eE][+-]?\d{1,2})?", text):
        return None
    try:
        value = Decimal(text)
        return value if value.is_finite() and 0 <= value <= Decimal("1e30") else None
    except InvalidOperation:
        return None


def canonical(category, text):
    if not isinstance(text, str) or len(text) > 128:
        return None
    text = text.strip().replace("µ", "u").replace("μ", "u")
    if category == "resistor":
        text = re.sub(r"(?:Ω|[Oo][Hh][Mm][Ss]?)$", "", text).strip()
        factors = {
            "": Decimal(1),
            "R": Decimal(1),
            "r": Decimal(1),
            "k": Decimal(1000),
            "K": Decimal(1000),
            "M": Decimal(1000000),
        }
    elif category == "capacitor":
        explicit_farad = text.endswith(("F", "f"))
        text = text[:-1] if explicit_farad else text
        factors = {
            "": Decimal(1),
            "p": Decimal("1e-12"),
            "n": Decimal("1e-9"),
            "u": Decimal("1e-6"),
            "m": Decimal("1e-3"),
        }
        # A bare number without an explicit F or prefix has no reliable unit.
        if not explicit_farad and not re.search("[pnum]", text):
            return None
    else:
        return None
    match = re.fullmatch(r"(\d+(?:\.\d+)?(?:[eE][+-]?\d{1,2})?)\s*([RrkKMpnum]?)", text)
    if match:
        value, suffix = number(match[1]), match[2]
    else:
        match = re.fullmatch(r"(\d+)([RrkKMpnum])(\d+)", text)
        if not match:
            return None
        value, suffix = number(match[1] + "." + match[3]), match[2]
    if value is None or suffix not in factors:
        return None
    with localcontext() as context:
        context.prec = 256
        result = value * factors[suffix]
    if category == "capacitor" and result <= 0:
        return None
    return decimal_text(result)


def decimal_text(value):
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def rating(text, kind):
    if not isinstance(text, str):
        return None
    text = text.strip()
    if kind == "tolerance":
        text = text.removeprefix("±").strip()
        if not text.endswith("%"):
            return None
        value = number(text[:-1].strip())
        return decimal_text(value) if value is not None and 0 < value <= 100 else None
    if kind == "voltage":
        match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(mV|V)?", text)
        if not match:
            return None
        value = number(match[1])
        if value is None or value <= 0:
            return None
        with localcontext() as context:
            context.prec = 256
            return decimal_text(value * (Decimal(".001") if match[2] == "mV" else 1))
    return None
