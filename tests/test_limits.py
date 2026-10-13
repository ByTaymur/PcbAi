import re
import unittest
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.verify.limits import LIMITS, require


class LimitTests(unittest.TestCase):
    def test_documented_ids_and_existing_evidence_match_registry(self):
        docs = Path(__file__).resolve().parents[1] / "docs"
        rows = [line for line in (docs / "limits.md").read_text(encoding="utf-8").splitlines()
                if line.startswith("| L-")]
        self.assertEqual({line.split("|")[1].strip() for line in rows}, set(LIMITS))
        for row in rows:
            paths = re.findall(r"\]\(([^)]+)\)", row)
            self.assertTrue(paths, row)
            for path in paths:
                self.assertTrue((docs / path.split("#")[0]).is_file(), row)
            self.assertTrue(require(row.split("|")[1].strip()))

    def test_unknown_limit_id_rejected(self):
        with self.assertRaises(PcbAiError):
            require("L-INVENTED")
