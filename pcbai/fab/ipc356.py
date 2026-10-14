"""Strict reader for the measured native KiCad IPC-D-356 subset."""
import re

from pcbai.core.contract import PcbAiError


def parse(raw):
    if len(raw) > 8 * 1024 * 1024:
        raise PcbAiError("invalid_ipc356", "IPC-D-356 exceeds size limit")
    try:
        text = raw.decode("ascii")
    except UnicodeError as exc:
        raise PcbAiError("invalid_ipc356", "Unsupported IPC-D-356 character encoding") from exc
    scale, ended, points, seen = None, False, [], set()
    for line in text.splitlines():
        if not line.strip():
            continue
        if ended:
            raise PcbAiError("invalid_ipc356", "Data follows IPC-D-356 terminator")
        if line.startswith("C"):
            continue
        if line.startswith("P"):
            if re.fullmatch(r"P\s+UNITS\s+CUST\s+0\s*", line):
                if scale is not None:
                    raise PcbAiError("invalid_ipc356", "Duplicate IPC units declaration")
                scale = .00254  # KiCad's measured CUST 0: one ten-thousandth inch.
            elif not re.fullmatch(r"P\s+(CODE\s+00|arrayDim\s+N)\s*", line):
                raise PcbAiError("unsupported_ipc356", "Unsupported IPC parameter")
            continue
        if line == "999":
            ended = True
            continue
        if line[:3] != "327":
            raise PcbAiError("unsupported_ipc356", "Only surface access points are calibrated; plated interlayer paths need drill evidence")
        if scale is None:
            raise PcbAiError("invalid_ipc356", "IPC access points precede units")
        net, ref, raw_pin = line[3:17].strip(), line[20:26].strip(), line[26:31].strip()
        pin = raw_pin.removeprefix("-")
        location = re.fullmatch(r"\s*A(01|02)X([+-]\d{6})Y([+-]\d{6})X\d{4}Y\d{4}R\d{3}S\d\s*", line[31:])
        if not ref or not pin or not net or location is None:
            raise PcbAiError("invalid_ipc356", "Malformed IPC surface access point")
        if len(net) >= 14:
            raise PcbAiError("unsupported_ipc356", "Full-width IPC net names may be truncated; alias authority is unverified")
        if len(ref) >= 6 or len(raw_pin) >= 5:
            raise PcbAiError("unsupported_ipc356", "Full-width IPC reference/pin identity may be truncated")
        key = (ref, pin)
        if key in seen:
            raise PcbAiError("invalid_ipc356", "Duplicate IPC reference/pin identity")
        seen.add(key)
        points.append(dict(reference=ref, pin=pin, net=net, layer="F.Cu" if location[1] == "01" else "B.Cu",
                           x_mm=int(location[2]) * scale, y_mm=int(location[3]) * scale))
        if len(points) > 10000:
            raise PcbAiError("invalid_ipc356", "Too many IPC access points")
    if scale is None or not ended:
        raise PcbAiError("invalid_ipc356", "IPC units or terminator missing")
    return dict(points=points, units="CUST 0", quantum_mm=scale, net_names_truncated=True,
                plated_paths_verified=False)
