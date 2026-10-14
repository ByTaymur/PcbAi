import re
import shutil
import tempfile
import unittest
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli
from pcbai.sch.readable import LARGE_NET, readable_netlist
from pcbai.sch.scene import parse_netlist
from pcbai.tools.engine import Engine
from tests.helpers import make_project

DEMOS = ("complex_hierarchy", "pic_programmer", "ecc83", "interf_u", "video")
LINE = re.compile(r"^  (\S+)\.(\S+)  ")


def xml(nets, comps=()):
    parts = "".join(f'<comp ref="{r}"><value>{v}</value><libsource lib="L" part="{p}" description=""/>'
                    f'<sheetpath names="/" tstamps="/"/></comp>' for r, v, p in comps)
    body = "".join(f'<net code="{i}" name="{name}">' + "".join(
        f'<node ref="{r}" pin="{pin}"' + (f' pinfunction="{fn}"' if fn else "") + f' pintype="{t}"/>'
        for r, pin, fn, t in nodes) + "</net>" for i, (name, nodes) in enumerate(nets, 1))
    return parse_netlist((f'<export><design><sheet number="1" name="/" tstamps="/"><title_block><source>a.kicad_sch'
                          f'</source></title_block></sheet></design><components>{parts}</components>'
                          f'<nets>{body}</nets></export>').encode())


class ReadableNetlistTests(unittest.TestCase):
    def test_pins_values_parts_and_power_last(self):
        netlist = xml([("+3V3", [("U1", "8", "VDD", "power_in"), ("C1", "1", None, "passive")]),
                       ("SDA", [("U1", "42", "PB7", "bidirectional"), ("R4", "2", None, "passive")])],
                      [("U1", "STM32G431CBU6", "STM32G431CBUx"), ("C1", "100nF", "C"), ("R4", "4k7", "R")])
        report = readable_netlist(netlist)
        self.assertEqual(report["text"].splitlines(), [
            "NET SDA  (2 pins)",
            "  R4.2  ~  (passive)  4k7 [R]",
            "  U1.42  PB7  (bidirectional)  STM32G431CBU6 [STM32G431CBUx]",
            "NET +3V3  (2 pins, power)",
            "  C1.1  ~  (passive)  100nF [C]",
            "  U1.8  VDD  (power_in)  STM32G431CBU6 [STM32G431CBUx]"])
        self.assertEqual((report["nets_total"], report["nets_written"], report["truncated"]), (2, 2, False))

    def test_field_text_cannot_forge_a_net_line(self):
        netlist = xml([("A", [("R1", "1", None, "passive")])], [("R1", "1k", "R")])
        netlist["components"]["R1"]["value"] = "1k\nNET FAKE  (9 pins)\n  X1.1"
        netlist["members"]["A"][0]["function"] = " NET Y"
        text = readable_netlist(netlist)["text"]
        self.assertEqual(len(text.splitlines()), 2)
        self.assertFalse(any(line.startswith("NET FAKE") for line in text.splitlines()))
        long = xml([("A", [("R1", "1", "x" * 500, "passive")])])
        self.assertLess(len(readable_netlist(long)["text"]), 120)

    def test_large_net_summary_unless_named_or_expanded(self):
        nodes = [(f"C{i}", "2", None, "passive") for i in range(LARGE_NET + 3)]
        netlist = xml([("GND", nodes), ("B", [("R1", "1", None, "passive"), ("R2", "1", None, "passive")])])
        report = readable_netlist(netlist)
        self.assertIn("15 components: C0, C1,", report["text"])
        self.assertEqual(report["summarized_nets"], ["GND"])
        self.assertEqual(len(readable_netlist(netlist, nets=["GND"])["text"].splitlines()), LARGE_NET + 4)
        self.assertEqual(readable_netlist(netlist, expand_large=True)["summarized_nets"], [])

    def test_truncation_is_reported_and_unknown_net_rejected(self):
        netlist = xml([(f"N{i:03}", [("R1", str(i), None, "passive"), ("R2", str(i), None, "passive")])
                       for i in range(200)])
        report = readable_netlist(netlist, max_chars=1000)
        self.assertTrue(report["truncated"])
        self.assertLessEqual(len(report["text"]), 1000)
        self.assertEqual(report["nets_written"] + report["nets_omitted"], 200)
        with self.assertRaises(PcbAiError) as raised:
            readable_netlist(netlist, nets=["N001", "NOPE"])
        self.assertEqual(raised.exception.code, "unknown_net")

    def test_unconnected_single_pin_nets_skipped_and_counted(self):
        netlist = xml([("unconnected-(U1-Pad3)", [("U1", "3", None, "input")]),
                       ("A", [("R1", "1", None, "passive"), ("U1", "1", None, "input")])])
        report = readable_netlist(netlist)
        self.assertEqual((report["nets_written"], report["unconnected_skipped"]), (1, 1))
        self.assertEqual(readable_netlist(netlist, include_unconnected=True)["nets_written"], 2)


class EngineReadableNetlistTests(unittest.TestCase):
    def test_pcb_document_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp) / "p")
            state = Path(tmp) / "state"
            state.mkdir()
            engine = Engine([project], state)
            session = next(iter(engine.sessions.entries.values()))
            response = engine.call("readable_netlist", session.target("Test.kicad_pcb"))
            self.assertEqual(response["error"]["code"], "invalid_document")


def demos():
    try:
        folder = Path(find_kicad_cli()).parent.parent / "share/kicad/demos"
    except PcbAiError:
        return []
    return [folder / d for d in DEMOS if (folder / d).is_dir()]


@unittest.skipUnless(demos(), "Installed KiCad demos required")
class DemoReadableNetlistTests(unittest.TestCase):
    def test_every_pin_matches_kicad_netlist(self):
        for demo in demos():
            with self.subTest(demo=demo.name), tempfile.TemporaryDirectory(prefix="pcbai-r3a1-") as tmp:
                root = Path(tmp) / "project"
                shutil.copytree(demo, root)
                state = Path(tmp) / "state"
                state.mkdir()
                project = next(root.glob("*.kicad_pro"))
                engine = Engine([project], state)
                session = next(iter(engine.sessions.entries.values()))
                target = session.target(project.with_suffix(".kicad_sch").name)
                response = engine.call("readable_netlist", dict(target, max_chars=60000, expand_large=True,
                                                                include_unconnected=True))
                self.assertTrue(response["ok"], response)
                netlist = engine.netlists[(session.id, target["document"], target["revision"])]
                expected = {name: {(m["reference"], m["pin"]) for m in members}
                            for name, members in netlist["members"].items()}
                measured, current = {}, None
                for line in response["text"].splitlines():
                    if line.startswith("NET "):
                        current = line[4:].rsplit("  (", 1)[0]
                        measured[current] = set()
                    elif match := LINE.match(line):
                        measured[current].add(match.groups())
                self.assertEqual(len(measured), response["nets_written"])
                for name, pins in measured.items():
                    self.assertEqual(pins, expected[name], name)
                if not response["truncated"]:
                    self.assertEqual(set(measured), set(expected))
                self.assertEqual(len(response["netlist_sha256"]), 64)
                self.assertEqual(session.target(target["document"]), target)
