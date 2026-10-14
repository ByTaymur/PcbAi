"""Independent bounded positive Gerber geometry subset, without net-label authority.

Circle/rectangle/obround flashes and circular-aperture linear strokes only.
Regions, arcs, clear polarity, macros, transforms and unknown commands fail closed.
"""
import re
from fractions import Fraction

from pcbai.core.contract import PcbAiError


def fail(message):
    raise PcbAiError("unsupported_gerber", message)


def parse(raw):
    if len(raw) > 8 * 1024 * 1024:
        fail("Gerber exceeds size limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        fail("Invalid Gerber text encoding")
    tokens = re.findall(r"%[^%]*%|[^%*]+\*", text)
    if re.sub(r"%[^%]*%|[^%*]+\*", "", text).strip():
        fail("Unterminated Gerber command")
    apertures, shapes = {}, []
    precision, units, layer, polarity = None, None, None, None
    point, aperture, pin, ended = None, None, None, False
    for token in tokens:
        token = token.strip()
        if ended:
            fail("Data after Gerber M02")
        if token.startswith("%"):
            command = token[1:-1]
            if not command.endswith("*"):
                fail("Invalid extended Gerber command")
            command = command[:-1]
            fmt = re.fullmatch(r"FSLAX([1-6])([1-6])Y\1\2", command)
            if fmt:
                if precision is not None:
                    fail("Duplicate coordinate format")
                precision = (int(fmt[1]), int(fmt[2]))
            elif command == "MOMM":
                if units is not None:
                    fail("Duplicate units declaration")
                units = "mm"
            elif command == "LPD":
                pass
            elif command.startswith("TF.FileFunction,"):
                match = re.fullmatch(r"TF.FileFunction,Copper,L([1-9][0-9]*),(Top|Bot|Inr)", command)
                if not match or layer is not None:
                    fail("Missing unique copper layer function")
                index = int(match[1])
                layer = "F.Cu" if match[2] == "Top" and index == 1 else "B.Cu" if match[2] == "Bot" else f"In{index-1}.Cu"
            elif command == "TF.FilePolarity,Positive":
                if polarity is not None:
                    fail("Duplicate file polarity")
                polarity = "positive"
            elif command.startswith(("TF.GenerationSoftware,", "TF.CreationDate,", "TF.ProjectId,", "TF.SameCoordinates,", "TA.", "TO.N,")):
                # Attributes are data; .N never determines physical connectivity.
                if "*" in command:
                    fail("Compound attributes unsupported")
            elif command.startswith("TO.P,"):
                fields = command.split(",")
                if len(fields) != 3 or not fields[1] or not fields[2] or "\\" in command:
                    fail("Unsupported pin attribute")
                pin = (fields[1], fields[2])
            elif command == "TD" or command == "TD.P":
                pin = None
            elif command == "TD.N":
                pass
            elif command.startswith("ADD"):
                match = re.fullmatch(r"ADD([1-9][0-9]*)(C|R|O),([0-9.]+)(?:X([0-9.]+))?", command)
                if not match:
                    fail("Unsupported aperture geometry")
                code, kind = int(match[1]), match[2]
                try:
                    if any(len(value) > 32 for value in (match[3], match[4]) if value is not None):
                        fail("Aperture numeric precision exceeds supported budget")
                    dimensions = [Fraction(value) for value in (match[3], match[4]) if value is not None]
                except ValueError:
                    fail("Malformed aperture dimension")
                if code < 10 or code in apertures or len(dimensions) != (1 if kind == "C" else 2):
                    fail("Invalid aperture declaration")
                if any(not 0 < value <= 100 for value in dimensions):
                    fail("Aperture dimensions exceed limits")
                apertures[code] = (kind, dimensions)
            else:
                fail("Unsupported Gerber extended command")
            continue
        command = token[:-1]
        if command.startswith("G04"):
            continue
        if command == "G01":
            continue
        if command == "M02":
            ended = True
            continue
        select = re.fullmatch(r"D([1-9][0-9]+)", command)
        if select and int(select[1]) >= 10:
            aperture = int(select[1])
            if aperture not in apertures:
                fail("Undefined aperture")
            continue
        operation = re.fullmatch(r"(?:X([+-]?\d+))?(?:Y([+-]?\d+))?D0([123])", command)
        if not operation or precision is None or units is None or not (operation[1] or operation[2]):
            fail("Unsupported Gerber plotting command")
        if any(value is not None and len(value.lstrip("+-")) > sum(precision) for value in operation.groups()[:2]):
            fail("Coordinate exceeds declared format")
        target = tuple(Fraction(int(value), 10**precision[1]) if value is not None else point[i] if point is not None else None
                       for i, value in enumerate(operation.groups()[:2]))
        if any(value is None or abs(value) > 100000 for value in target):
            fail("Undefined or out-of-range coordinate")
        op = operation[3]
        if op != "2":
            if aperture not in apertures:
                fail("Plot without aperture")
            kind, size = apertures[aperture]
            if op == "1":
                if point is None or kind != "C":
                    fail("Only circular-aperture linear strokes supported")
                shape = dict(kind="capsule", a=point, b=target, radius=size[0]/2)
            elif kind == "R":
                shape = dict(kind="rect", center=target, width=size[0], height=size[1])
            elif kind == "C":
                shape = dict(kind="capsule", a=target, b=target, radius=size[0]/2)
            else:
                width, height = size
                offset = ((width-height)/2, 0) if width >= height else (0, (height-width)/2)
                shape = dict(kind="capsule", a=(target[0]-offset[0], target[1]-offset[1]),
                             b=(target[0]+offset[0], target[1]+offset[1]), radius=min(size)/2)
            shape.update(pin=pin if op == "3" else None, center_mm=tuple(float(v) for v in target) if op == "3" else None)
            shapes.append(shape)
            if len(shapes) > 500:
                fail("Geometry pair-comparison budget exceeded")
        point = target
    if not ended or precision is None or units is None or layer is None or polarity is None:
        fail("Incomplete Gerber header or terminator")
    return dict(layer=layer, shapes=shapes, coordinate_quantum_mm=10**-precision[1], coverage="supported_subset")


def point_distance_squared(p, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    scale = dx*dx + dy*dy
    t = max(0, min(1, ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/scale)) if scale else 0
    return (p[0]-a[0]-t*dx)**2 + (p[1]-a[1]-t*dy)**2


def segment_distance_squared(a, b, c, d):
    def cross(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    if cross(a, b, c)*cross(a, b, d) <= 0 and cross(c, d, a)*cross(c, d, b) <= 0:
        if (max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0]))
                and max(min(a[1], b[1]), min(c[1], d[1])) <= min(max(a[1], b[1]), max(c[1], d[1]))):
            return 0
    return min(point_distance_squared(a, c, d), point_distance_squared(b, c, d),
               point_distance_squared(c, a, b), point_distance_squared(d, a, b))


def rectangle(shape):
    x, y = shape["center"]
    w, h = shape["width"]/2, shape["height"]/2
    return [(x-w, y-h), (x+w, y-h), (x+w, y+h), (x-w, y+h)]


def intersects(left, right):
    if left["kind"] == right["kind"] == "capsule":
        return segment_distance_squared(left["a"], left["b"], right["a"], right["b"]) <= (left["radius"]+right["radius"])**2
    if left["kind"] == right["kind"] == "rect":
        return (abs(left["center"][0]-right["center"][0])*2 <= left["width"]+right["width"]
                and abs(left["center"][1]-right["center"][1])*2 <= left["height"]+right["height"])
    capsule, rect = (left, right) if left["kind"] == "capsule" else (right, left)
    corners = rectangle(rect)
    for p in (capsule["a"], capsule["b"]):
        if corners[0][0] <= p[0] <= corners[2][0] and corners[0][1] <= p[1] <= corners[2][1]:
            return True
    return min(segment_distance_squared(capsule["a"], capsule["b"], a, b)
               for a, b in zip(corners, corners[1:]+corners[:1], strict=True)) <= capsule["radius"]**2


def islands(shapes):
    parents = list(range(len(shapes)))
    bounds = []
    for shape in shapes:
        if shape["kind"] == "rect":
            corners = rectangle(shape)
            bounds.append((*corners[0], *corners[2]))
        else:
            a, b, radius = shape["a"], shape["b"], shape["radius"]
            bounds.append((min(a[0], b[0])-radius, min(a[1], b[1])-radius,
                           max(a[0], b[0])+radius, max(a[1], b[1])+radius))

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for i, left in enumerate(shapes):
        for j in range(i):
            if (bounds[i][0] > bounds[j][2] or bounds[j][0] > bounds[i][2]
                    or bounds[i][1] > bounds[j][3] or bounds[j][1] > bounds[i][3]):
                continue
            if intersects(left, shapes[j]):
                parents[root(i)] = root(j)
    return [root(index) for index in range(len(shapes))]
