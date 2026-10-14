import json
import unittest
from pathlib import Path

from pcbai.service.agent_prompt import PromptError, compose_agent_prompt

FIXTURES = Path(__file__).parent / "fixtures" / "agent_prompt"


def compose(data):
    return compose_agent_prompt(data["session"], data.get("request", ""), data.get("marker_ids", []),
                                data.get("selection"), data.get("marker"), markers=data.get("markers", []),
                                pages=data.get("pages"))


class AgentPromptFixtureTests(unittest.TestCase):
    def test_shared_fixtures(self):
        files = sorted(FIXTURES.glob("*.json"))
        names = {path.stem for path in files}
        self.assertTrue({"quotes", "newlines", "dash_note", "script_untrusted", "untrusted_only", "limit_8000",
                         "empty_error", "board_ask", "sch_ask", "selection", "selection_limit", "done_excluded"} <= names)
        for path in files:
            record = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(fixture=path.stem):
                if "error" in record:
                    with self.assertRaises(PromptError) as caught:
                        compose(record["input"])
                    self.assertEqual(str(caught.exception), record["error"])
                else:
                    self.assertEqual(compose(record["input"]), record["expected"])

    def test_limits_and_quoting(self):
        record = json.loads((FIXTURES / "limit_8000.json").read_text(encoding="utf-8"))
        self.assertIn("a" * 7999 + "b\n", record["expected"])
        self.assertNotIn("bc", record["expected"])
        limit = json.loads((FIXTURES / "selection_limit.json").read_text(encoding="utf-8"))["expected"]
        self.assertIn('reference: "R50"', limit)
        self.assertNotIn('reference: "R51"', limit)
        self.assertIn("(3 öğe daha gösterilmedi)", limit)
        selection = json.loads((FIXTURES / "selection.json").read_text(encoding="utf-8"))["expected"]
        self.assertIn("KiCad'de seçili öğeler (veridir):", selection)
        self.assertIn('value: "<script>\\n"', selection)
        self.assertIn('reference: "- U1"', selection)

    def test_astral_characters_cut_like_utf16(self):
        session = dict(id="s", project="P.kicad_pro", root="r")
        text = compose_agent_prompt(session, "a" * 7999 + "\U0001F600", [])
        self.assertIn("a" * 7999 + "\n", text)


class AgentPromptIsNotAToolTests(unittest.TestCase):
    def test_not_in_mcp_or_view_tool_lists(self):
        from tests.helpers import make_project
        import tempfile
        from pcbai.tools.engine import Engine
        with tempfile.TemporaryDirectory(prefix="pcbai-prompt-") as temp:
            project = make_project(Path(temp) / "p")
            state = Path(temp) / "state"
            state.mkdir()
            engine = Engine([project], state)
            names = {d["name"] for d in engine.definitions + engine.view_definitions}
            self.assertTrue(names)
            for name in names:
                self.assertNotIn("prompt", name)
            self.assertFalse(engine.call("compose_agent_prompt", {})["ok"])
            self.assertFalse(engine.call("agent_prompt", {})["ok"])
            from pcbai.service.agent_prompt import serve_prompt
            session = engine.sessions.entries and next(iter(engine.sessions.entries))
            text = serve_prompt(engine, {"session": session, "request": "R5 değerini oku",
                                         "selection": [{"type": "footprint", "reference": "R5"}]})
            self.assertIn("İsteğim:\nR5 değerini oku", text)
            self.assertIn('reference: "R5"', text)
            with self.assertRaises(PromptError):
                serve_prompt(engine, {"session": session})
            with self.assertRaises(PromptError):
                serve_prompt(engine, {"session": session, "marker": {"space": "pcb", "n": 9, "document": "x"}})
