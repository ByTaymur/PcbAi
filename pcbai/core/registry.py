import math

from pcbai.core.contract import PcbAiError


def validate(schema, value, path="arguments"):
    expected = schema.get("type")
    types = {"object": dict, "string": str, "boolean": bool, "integer": int, "number": (int, float), "array": list}
    if expected and (not isinstance(value, types[expected])
                     or (expected in {"integer", "number"} and isinstance(value, bool))):
        raise PcbAiError("invalid_arguments", f"{path} must be {expected}")
    if "enum" in schema and value not in schema["enum"]:
        raise PcbAiError("invalid_arguments", f"{path} must be one of {schema['enum']}")
    if expected in {"integer", "number"} and (not math.isfinite(value) or
            not schema.get("minimum", value) <= value <= schema.get("maximum", value)):
        raise PcbAiError("invalid_arguments", f"{path} is outside the allowed range")
    if expected == "string" and (len(value) > schema.get("maxLength", 4096) or "\0" in value):
        raise PcbAiError("invalid_arguments", f"{path} contains invalid text or is too long")
    if expected == "object":
        props = schema.get("properties", {})
        unknown = set(value) - set(props)
        if unknown and schema.get("additionalProperties") is False:
            raise PcbAiError("invalid_arguments", f"Unknown arguments: {', '.join(sorted(unknown))}")
        missing = set(schema.get("required", [])) - set(value)
        if missing:
            raise PcbAiError("invalid_arguments", f"Required: {', '.join(sorted(missing))}")
        for key in value:
            if key in props:
                validate(props[key], value[key], path + "." + key)
    if expected == "array":
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 10000):
            raise PcbAiError("invalid_arguments", f"{path} has an invalid item count")
        if "items" in schema:
            for index, item in enumerate(value):
                validate(schema["items"], item, f"{path}[{index}]")


def schema(properties=None, required=()):
    return dict(type="object", properties=properties or {}, required=list(required), additionalProperties=False)


STRING = {"type": "string", "maxLength": 4096}
TARGET = {"session": STRING, "document": STRING}
