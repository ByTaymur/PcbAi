"""Closed built-in passive recipes. Only trusted code expands component intents."""
import copy

from jsonschema import Draft202012Validator

from pcbai.blocks.compute import calculate
from pcbai.core.contract import PcbAiError

QTY = {"oneOf": [{"type": "number"}, {"type": "string", "minLength": 1, "maxLength": 80}]}


def params(properties, required):
    return dict(type="object", properties=properties, required=required, additionalProperties=False)


RECIPES = {
    "voltage_divider": dict(version=1, maturity=0, category="passive",
        params=params(dict(vin=QTY, r_top=QTY, r_bottom=QTY, r_load=QTY), ["vin", "r_top", "r_bottom"]),
        ports={"IN": "analog", "OUT": "analog", "GND": "ground"}, calculation="divider"),
    "rc_filter": dict(version=1, maturity=0, category="passive",
        params=params(dict(r=QTY, c=QTY, type={"enum": ["lowpass", "highpass"]}), ["r", "c"]),
        ports={"IN": "analog", "OUT": "analog", "GND": "ground"}, calculation="rc_filter"),
    "button_debounce": dict(version=1, maturity=0, category="passive",
        params=params(dict(r=QTY, c=QTY, direction={"enum": ["pullup", "pulldown"]}), ["r", "c", "direction"]),
        ports={"SUPPLY": "power_in", "INPUT": "signal", "OUT": "signal", "GND": "ground"},
        calculation="button_debounce")}

R_FOOTPRINT = "Resistor_SMD:R_0603_1608Metric"
C_FOOTPRINT = "Capacitor_SMD:C_0603_1608Metric"


def describe():
    return [dict(id=name, **copy.deepcopy(recipe), verified=False, stock_verified=False,
                 maturity_basis="Draft: recipe-level ERC/SPICE/hardware acceptance not recorded") for name, recipe in RECIPES.items()]


def expand(name, values):
    if name not in RECIPES:
        raise PcbAiError("unknown_block", "Supported built-in blocks: " + ", ".join(RECIPES))
    recipe = RECIPES[name]
    errors = list(Draft202012Validator(recipe["params"]).iter_errors(values))
    if errors:
        raise PcbAiError("invalid_block_parameters", errors[0].message,
                         details={"path": list(errors[0].path), "block": name, "schema": recipe["params"]})
    inputs = {k: v for k, v in values.items() if k not in {"type", "direction"}}
    calculated = calculate(recipe["calculation"], inputs)
    normal = calculated["normalized_inputs"]
    if name == "voltage_divider":
        parts = [("R1", "Device:R", R_FOOTPRINT, normal["r_top"]), ("R2", "Device:R", R_FOOTPRINT, normal["r_bottom"])]
        connections = {"IN": [("R1", "1")], "OUT": [("R1", "2"), ("R2", "1")], "GND": [("R2", "2")]}
        if "r_load" in normal:
            parts.append(("RL", "Device:R", R_FOOTPRINT, normal["r_load"]))
            connections["OUT"].append(("RL", "1"))
            connections["GND"].append(("RL", "2"))
    else:
        parts = [("R1", "Device:R", R_FOOTPRINT, normal["r"]), ("C1", "Device:C", C_FOOTPRINT, normal["c"])]
        if name == "rc_filter":
            first, shunt = ("C1", "R1") if values.get("type", "lowpass") == "highpass" else ("R1", "C1")
            connections = {"IN": [(first, "1")], "OUT": [(first, "2"), (shunt, "1")], "GND": [(shunt, "2")]}
        else:
            source = "SUPPLY" if values["direction"] == "pullup" else "GND"
            connections = {source: [("R1", "1")], "INPUT": [], "OUT": [("R1", "2"), ("C1", "1")], "GND": [("C1", "2")]}
            # INPUT is the external switch/contact node; its tie to OUT is explicit.
            connections["INPUT"] = connections["OUT"].copy()
            if source == "GND":
                connections["GND"].append(("R1", "1"))
            connections.setdefault("SUPPLY", [])
    active_ports = {port: kind for port, kind in recipe["ports"].items() if connections.get(port)}
    return dict(block=name, version=recipe["version"], maturity=0,
                parts=[dict(id=id, symbol=symbol, footprint=fp, value=f"{value:.12g}", value_si=value,
                            verified=False, stock_verified=False) for id, symbol, fp, value in parts],
                ports=active_ports, port_pins={key: [dict(part=part, pin=pin) for part, pin in pins]
                                             for key, pins in connections.items() if pins},
                calculation=calculated, warnings=["Block maturity is 0; no recipe-level acceptance or stock verification"] + calculated["warnings"])
