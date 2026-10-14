import unittest

from pcbai.doctor import kicad_version_tuple, requirements


def cli(version, available=True):
    parsed = kicad_version_tuple(version)
    return {"kicad_cli": {"available": available, "version": version,
                          "supported": parsed is not None and parsed[:2] == (10, 0) and parsed >= (10, 0, 7)}}


class KiCadVersionRequirementTests(unittest.TestCase):
    def test_parsing(self):
        self.assertEqual(kicad_version_tuple("10.0.7"), (10, 0, 7))
        self.assertEqual(kicad_version_tuple("10.0"), (10, 0, 0))
        self.assertEqual(kicad_version_tuple("10.99.0-1234-gabc"), (10, 99, 0))
        self.assertIsNone(kicad_version_tuple("ten"))

    def test_only_10_0_7_and_later_10_0_are_supported(self):
        for version, ok in [("10.0.4", False), ("10.0.6", False), ("10.0.7", True), ("10.0.9", True),
                            ("10.99.0", False), ("11.0.0", False), ("9.0.7", False)]:
            with self.subTest(version=version):
                self.assertEqual(requirements(cli(version)) == [], ok)
        self.assertIn("kicad-cli", requirements(cli("", available=False))[0])
