"""Iterative KiCad concrete syntax reader. Offsets are bytes, never character offsets."""
import json
from dataclasses import dataclass, field

from pcbai.core.contract import PcbAiError


@dataclass
class Node:
    start: int
    end: int
    atom: str | None = None
    children: list = field(default_factory=list)

    @property
    def name(self):
        return self.children[0].atom if self.children else None

    def all(self, name):
        return [n for n in self.children if n.atom is None and n.name == name]

    def child(self, name):
        return next(iter(self.all(name)), None)

    def value(self, index=1, default=None):
        return self.children[index].atom if len(self.children) > index else default


class Document:
    def __init__(self, data):
        if not isinstance(data, bytes):
            raise TypeError("S-expression input must be bytes")
        self.data = data
        self.root = self._parse()

    def _parse(self):
        data, stack, roots, i = self.data, [], [], 0
        while i < len(data):
            byte = data[i]
            if byte in b" \t\r\n":
                i += 1
                continue
            if byte == 59:  # comments are preserved in the source
                end = data.find(b"\n", i)
                i = len(data) if end < 0 else end + 1
                continue
            if byte == 40:
                node = Node(i, 0)
                (stack[-1].children if stack else roots).append(node)
                stack.append(node)
                i += 1
            elif byte == 41:
                if not stack:
                    raise PcbAiError("invalid_sexpr", f"Unexpected ')' at byte {i}")
                stack.pop().end = i + 1
                i += 1
            else:
                start = i
                if byte == 34:
                    i += 1
                    while i < len(data):
                        if data[i] == 92:
                            i += 2
                        elif data[i] == 34:
                            i += 1
                            break
                        else:
                            i += 1
                    else:
                        raise PcbAiError("invalid_sexpr", "Unterminated string")
                    try:
                        # KiCad accepts literal tab/newline characters inside quoted text.
                        atom = json.loads(data[start:i].decode("utf-8"), strict=False)
                    except (ValueError, UnicodeError) as exc:
                        raise PcbAiError("invalid_sexpr", "Invalid quoted UTF-8 string") from exc
                else:
                    while i < len(data) and data[i] not in b"() \t\r\n;":
                        i += 1
                    try:
                        atom = data[start:i].decode("utf-8")
                    except UnicodeError as exc:
                        raise PcbAiError("invalid_sexpr", "Invalid UTF-8 atom") from exc
                (stack[-1].children if stack else roots).append(Node(start, i, atom=atom))
        if stack or len(roots) != 1 or roots[0].atom is not None:
            raise PcbAiError("invalid_sexpr", "Expected one complete root expression")
        return roots[0]

    def serialize(self):
        return self.data

    def replace_string(self, node, value):
        if node.atom is None or self.data[node.start:node.start + 1] != b'"':
            raise PcbAiError("invalid_edit", "Only an existing quoted atom can be replaced")
        encoded = json.dumps(value, ensure_ascii=False).encode("utf-8")
        changed = self.data[:node.start] + encoded + self.data[node.end:]
        Document(changed)
        return changed
