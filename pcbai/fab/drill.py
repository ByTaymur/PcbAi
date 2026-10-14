"""Independent counts for the native absolute metric decimal Excellon subset."""
import math
import re

from pcbai.core.contract import PcbAiError

NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
XY = rf"X({NUMBER})Y({NUMBER})"


def fail(message):
    raise PcbAiError("unsupported_drill", message)


def parse(raw):
    if len(raw) > 8 * 1024 * 1024:
        fail("Drill file exceeds size limit")
    try:
        text = raw.decode("ascii")
    except UnicodeError:
        fail("Unsupported drill character encoding")
    header, started, metric, decimal, ended, tools, tool = False, False, False, False, False, {}, None
    hits, slots = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ended:
            fail("Data follows drill M30")
        if line.startswith(";"):
            if line.startswith("; FORMAT="):
                if not header or decimal or not re.fullmatch(r"; FORMAT=\{-:-/\s*absolute\s*/\s*metric\s*/\s*decimal\s*\}", line):
                    fail("Unsupported or duplicate native drill format")
                decimal = True
            continue
        if line == "M48":
            if started:
                fail("Duplicate drill header")
            header, started = True, True
            continue
        if header:
            if line == "METRIC":
                if metric:
                    fail("Duplicate drill units")
                metric = True
            elif line == "FMAT,2":
                pass
            elif line == "%":
                if not metric or not decimal:
                    fail("Uncalibrated drill units or coordinate format")
                header = False
            else:
                definition = re.fullmatch(rf"T([1-9][0-9]*)C({NUMBER})", line)
                if not definition:
                    fail("Unsupported drill header command")
                identifier, diameter = int(definition[1]), float(definition[2])
                if identifier in tools or not math.isfinite(diameter) or not 0 < diameter <= 100:
                    fail("Invalid drill tool")
                tools[identifier] = diameter
            continue
        if not started:
            fail("Drill data precedes header")
        if line in {"G90", "G05"}:
            continue
        if line == "M30":
            if not metric or not decimal:
                fail("Incomplete drill header")
            ended = True
            continue
        selection = re.fullmatch(r"T([0-9]+)", line)
        if selection:
            tool = int(selection[1]) or None
            if tool is not None and tool not in tools:
                fail("Undefined drill tool")
            continue
        slot = re.fullmatch(XY + "G85" + XY, line)
        hit = re.fullmatch(XY, line)
        match = slot or hit
        if not match or tool is None or not metric or not decimal:
            fail("Unsupported drill command or coordinates")
        coordinates = [float(value) for value in match.groups()]
        if any(not math.isfinite(value) or abs(value) > 100000 for value in coordinates):
            fail("Drill coordinates exceed limits")
        record = dict(coordinates_mm=coordinates, diameter_mm=tools[tool])
        (slots if slot else hits).append(record)
        if len(hits)+len(slots) > 200000:
            fail("Drill count budget exceeded")
    if not ended or header:
        fail("Drill terminator missing")
    return dict(hits=hits, slots=slots, units="mm", origin="absolute", plating_verified=False)
