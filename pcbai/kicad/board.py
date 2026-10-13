"""Saved-board connectivity inspection. Pad coordinates remain footprint-local."""
from pcbai.core.contract import PcbAiError
from pcbai.sch.model import properties, position
from pcbai.sexpr import Document


def board(data):
    root = Document(data).root
    if root.name != "kicad_pcb":
        raise PcbAiError("invalid_document", "Expected a KiCad PCB")
    return root


def nets(root):
    """Net table of a KiCad ≤9 board; KiCad 10 boards name nets on items (number is then None)."""
    records = []
    for node in root.all("net"):
        try:
            number = int(node.value())
        except (ValueError, TypeError) as exc:
            raise PcbAiError("invalid_document", "PCB net has an invalid number") from exc
        name = node.value(2)
        if number < 0 or not isinstance(name, str):
            raise PcbAiError("invalid_document", "PCB net has an invalid number or name")
        records.append(dict(number=number, name=name, trusted=False))
    if len({n["number"] for n in records}) != len(records) or len({n["name"] for n in records}) != len(records):
        raise PcbAiError("invalid_document", "PCB has duplicate net numbers or names")
    if records:
        return records
    found = set()

    def visit(node):
        for child in node.children:
            if child.atom is None:
                if child.name == "net" and child.value() is not None and child.value(2) is None:
                    found.add(child.value())
                else:
                    visit(child)
    visit(root)
    found.discard("")
    return [dict(number=None, name=name, trusted=False) for name in sorted(found)]


def summary(data):
    root = board(data)
    layer_node = root.child("layers")
    layers = [dict(number=int(n.name), name=n.value(), type=n.value(2))
              for n in layer_node.children[1:]] if layer_node else []
    return dict(net_count=len([n for n in nets(root) if n["number"] != 0]), layers=layers,
                copper_layer_count=sum(layer["name"].endswith(".Cu") for layer in layers),
                footprint_count=len(root.all("footprint")),
                track_segment_count=len(root.all("segment")), via_count=len(root.all("via")))


def net_info(data, name):
    root = board(data)
    matches = [n for n in nets(root) if n["name"] == name]
    if not matches:
        raise PcbAiError("unknown_net", "Net name is absent from this saved PCB")
    net = matches[0]

    def matches_net(node):
        entry = node.child("net")
        if net["number"] is None:  # KiCad 10: items carry the net name
            return entry is not None and entry.value() == name and entry.value(2) is None
        if entry is None:
            return net["number"] == 0
        try:
            number = int(entry.value())
        except (ValueError, TypeError) as exc:
            raise PcbAiError("invalid_document", "Item has an invalid net number") from exc
        if entry.value(2) is not None and number == net["number"] and entry.value(2) != name:
            raise PcbAiError("invalid_document", "Pad net name and board definition disagree")
        return number == net["number"]

    pads = []
    for footprint in root.all("footprint"):
        props = properties(footprint)
        reference = props.get("Reference")
        if reference is None:
            reference = next((t.value(2) for t in footprint.all("fp_text") if t.value() == "reference"), None)
        for pad in footprint.all("pad"):
            if matches_net(pad):
                pads.append(dict(reference=reference, pad=pad.value(), at_local=position(pad),
                                 footprint_at=position(footprint), trusted=False))
    return dict(net=net, pads=pads, track_segment_count=sum(matches_net(n) for n in root.all("segment")),
                via_count=sum(matches_net(n) for n in root.all("via")),
                connectivity_verified=False)
