"""AJ-5: KiCad → VS Code handoff records are id-only, single use, expire after 10 minutes and carry the outcome back."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pcbai.core.contract import PcbAiError
from pcbai.service.handoff import LIFETIME, Handoffs


class HandoffTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.state = Path(temp.name)
        self.now = [1000.0]
        self.store = Handoffs(self.state, clock=lambda: self.now[0])
        self.session = SimpleNamespace(id="s-1", root=Path("C:/p"), project="motor.kicad_pro")

    def test_single_use_and_outcome(self):
        handoff_id = self.store.create(self.session, "R5 değerini oku")
        self.assertEqual(self.store.status(handoff_id), dict(id=handoff_id, taken=False, outcome=None, message=None))
        with self.assertRaises(PcbAiError):
            self.store.report(handoff_id, "typed")  # not taken yet
        taken = self.store.take(handoff_id)
        self.assertEqual((taken["prompt"], taken["session"]), ("R5 değerini oku", "s-1"))
        self.assertTrue(taken["project"].endswith("motor.kicad_pro"))
        self.assertNotIn("R5", (self.state / "handoff" / f"{handoff_id}.json").read_text(encoding="utf-8"))
        with self.assertRaises(PcbAiError) as caught:
            self.store.take(handoff_id)
        self.assertEqual(caught.exception.code, "already_taken")
        self.store.report(handoff_id, "typed", "Claude Code mesaj kutusuna yazıldı")
        self.assertEqual(self.store.status(handoff_id)["outcome"], "typed")
        with self.assertRaises(PcbAiError):
            self.store.report(handoff_id, "hacked")

    def test_expiry_and_bad_ids(self):
        handoff_id = self.store.create(self.session, "x")
        self.now[0] += LIFETIME + 1
        with self.assertRaises(PcbAiError) as caught:
            self.store.take(handoff_id)
        self.assertEqual(caught.exception.code, "expired")
        self.assertFalse((self.state / "handoff" / f"{handoff_id}.json").exists())
        for bad in ["../service", "x" * 36, None, 5]:
            with self.assertRaises(PcbAiError):
                self.store.take(bad)
        with self.assertRaises(PcbAiError):
            self.store.take("0f8fad5b-d9cb-469f-a165-70867728950e")

    def test_old_records_are_purged_and_prompt_validated(self):
        old = self.store.create(self.session, "eski")
        self.now[0] += LIFETIME + 5
        self.store.create(self.session, "yeni")
        self.assertFalse((self.state / "handoff" / f"{old}.json").exists())
        for prompt in ["", "   ", "x" * 70000, None]:
            with self.assertRaises(PcbAiError):
                self.store.create(self.session, prompt)


if __name__ == "__main__":
    unittest.main()
