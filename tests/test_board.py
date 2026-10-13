import unittest

from pcbai.core.contract import PcbAiError
from pcbai.kicad.board import net_info, summary
from tests.helpers import PCB


BOARD = PCB.replace(b'(property "Value" "10k")))', b'''(property "Value" "10k")
  (pad "1" smd rect (at 1 2) (net 1 "GND"))
  (pad "2" smd rect (at 3 4) (net 2 "+3V3")))
  (segment (start 1 2) (end 3 4) (net 1)) (via (at 3 4) (net 1)))''')


class BoardTests(unittest.TestCase):
    def test_net_membership_uses_exact_net_and_keeps_local_coordinates(self):
        output = net_info(BOARD, "GND")
        self.assertEqual([(p["reference"], p["pad"]) for p in output["pads"]], [("R1", "1")])
        self.assertEqual(output["pads"][0]["at_local"], [1.0, 2.0])
        self.assertEqual(output["pads"][0]["footprint_at"], [10.0, 20.0, 90.0])
        self.assertEqual(output["track_segment_count"], 1)
        self.assertEqual(output["via_count"], 1)
        self.assertFalse(output["connectivity_verified"])
        self.assertEqual(net_info(BOARD, "+3V3")["track_segment_count"], 0)

    def test_duplicate_unknown_or_inconsistent_nets_fail(self):
        for data, name in [(BOARD, "unknown"), (BOARD.replace(b'(net 2 "+3V3")', b'(net 1 "+3V3")', 1), "GND"),
                           (BOARD.replace(b'(net 1 "GND"))', b'(net 1 "WRONG"))'), "GND")]:
            with self.subTest(name=name), self.assertRaises(PcbAiError):
                net_info(data, name)

    def test_summary_counts_copper_layers_nets_and_items(self):
        data = BOARD.replace(b'(net 0', b'(layers (0 "F.Cu" signal) (2 "In1.Cu" power) '
                             b'(31 "B.Cu" signal) (44 "Edge.Cuts" user)) (net 0', 1)
        counts = summary(data)
        self.assertEqual(counts["copper_layer_count"], 3)
        self.assertEqual(counts["net_count"], 2)
        self.assertEqual(counts["footprint_count"], 1)
