"""Short-lived ngspice worker: KiCad's shared ngspice library driven through ctypes in its own process.

stdin: JSON {"library": path, "codemodels": [paths], "netlist": [lines], "commands": [..], "vectors": [names],
             "max_points": n}. Netlist text is SPICE data for the simulator; nothing is executed by Python.
stdout: one JSON object. A crash or hang of the simulator kills only this process (caller enforces a timeout).
"""
import ctypes
import json
import math
import os
import sys
from pathlib import Path


class VectorInfo(ctypes.Structure):
    _fields_ = [("v_name", ctypes.c_char_p), ("v_type", ctypes.c_int), ("v_flags", ctypes.c_short),
                ("v_realdata", ctypes.POINTER(ctypes.c_double)), ("v_compdata", ctypes.c_void_p),
                ("v_length", ctypes.c_int)]


SEND_CHAR = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
SEND_STAT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
EXIT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
SEND_DATA = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p)
INIT_DATA = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
BG_RUNNING = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)

COMPLEX = 2  # ngspice vector flags: VF_REAL = 1, VF_COMPLEX = 2


def short_path(path):
    path = Path(path)
    if os.name != "nt" or " " not in str(path):
        return path
    buffer = ctypes.create_unicode_buffer(1024)
    if not ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, 1024) or " " in buffer.value:
        raise RuntimeError("Code model path contains spaces and has no short name")
    return Path(buffer.value)


def finite(value):
    return value if math.isfinite(value) else None


def simulate(request):
    library = Path(request["library"])
    if os.name == "nt":
        os.add_dll_directory(str(library.parent))
    spice = ctypes.CDLL(str(library))
    log, exited = [], []

    @SEND_CHAR
    def on_char(text, _id, _user):
        if len(log) < 4000:
            log.append(text.decode("utf-8", "replace"))
        return 0

    @SEND_STAT
    def on_stat(_text, _id, _user):
        return 0

    @EXIT
    def on_exit(status, _unload, _quit, _id, _user):
        exited.append(status)
        return 0

    noop_data = SEND_DATA(lambda *_: 0)
    noop_init = INIT_DATA(lambda *_: 0)
    noop_bg = BG_RUNNING(lambda *_: 0)
    spice.ngSpice_Init(on_char, on_stat, on_exit, noop_data, noop_init, noop_bg, None)
    spice.ngGet_Vec_Info.restype = ctypes.POINTER(VectorInfo)
    spice.ngSpice_CurPlot.restype = ctypes.c_char_p
    spice.ngSpice_AllVecs.restype = ctypes.POINTER(ctypes.c_char_p)
    for model in request.get("codemodels", []):
        # ngspice splits "codemodel" arguments at spaces and does not unquote: use the 8.3 path on Windows.
        spice.ngSpice_Command(f"codemodel {short_path(model).as_posix()}".encode())
    lines = [line.encode("utf-8") for line in request["netlist"]]
    array = (ctypes.c_char_p * (len(lines) + 1))(*lines, None)
    if spice.ngSpice_Circ(array) != 0:
        return dict(ok=False, error="netlist_rejected", log=log[-60:])
    for command in request.get("commands", ["run"]):
        spice.ngSpice_Command(command.encode())
    if exited:
        return dict(ok=False, error="simulator_exited", log=log[-60:])
    plot = spice.ngSpice_CurPlot().decode()
    names = []
    pointer = spice.ngSpice_AllVecs(plot.encode())
    index = 0
    while pointer and pointer[index] and index < 10000:
        names.append(pointer[index].decode())
        index += 1
    wanted = request.get("vectors") or names
    limit = int(request.get("max_points", 20000))
    vectors = {}
    for name in wanted:
        info = spice.ngGet_Vec_Info(f"{plot}.{name}".encode())
        if not info:
            continue
        vector = info.contents
        length = vector.v_length
        if not vector.v_realdata and not vector.v_compdata:
            continue
        if vector.v_flags & COMPLEX and vector.v_compdata:
            # Complex (AC) data: magnitude and phase from the interleaved real/imaginary doubles.
            data = ctypes.cast(vector.v_compdata, ctypes.POINTER(ctypes.c_double))
            pairs = [(data[2 * i], data[2 * i + 1]) for i in range(length)]
            values = dict(real=[finite(a) for a, _ in pairs], imag=[finite(b) for _, b in pairs])
        else:
            values = [finite(vector.v_realdata[i]) for i in range(length)]
        if length > limit:
            step = math.ceil(length / limit)
            values = ({k: v[::step] for k, v in values.items()} if isinstance(values, dict) else values[::step])
        vectors[name] = dict(length=length, decimated=length > limit, values=values)
    errors = [line for line in log if "error" in line.lower()]
    return dict(ok=True, plot=plot, available=names, vectors=vectors, errors=errors[-20:], log=log[-60:])


def main():
    try:
        request = json.loads(sys.stdin.read(16 * 1024 * 1024))
        output = simulate(request)
    except Exception as exc:  # reported as data; the caller decides
        output = dict(ok=False, error="worker_failed", message=str(exc)[:500])
    sys.stdout.write(json.dumps(output, allow_nan=False))
    sys.stdout.flush()
    os._exit(0)  # ngspice's own atexit handlers are not needed and can hang


if __name__ == "__main__":
    main()
