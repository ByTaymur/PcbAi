"""AJ-6: built-in model loop and providers. Tools run in a real Engine; providers are scripted, served by a local
fake HTTP server (Ollama / OpenAI protocol) or a fake anthropic module. No real model or key is used here."""
import json
import os
import sys
import tempfile
import threading
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

from kicad_plugin import assistant_model as model
from pcbai.tools.engine import Engine
from tests.helpers import make_project

SECRET = "sk-ant-test-SECRET-0123456789"


class EngineClient:
    """The service API the window's client offers, backed by an in-process Engine."""

    def __init__(self, engine):
        self.engine = engine
        self.client_name = "builtin"

    def request(self, method, path, payload=None):
        if path == "/tools":
            return {"tools": self.engine.definitions}
        return self.engine.call(payload["name"], payload["arguments"], client=self.client_name)


class Scripted:
    """Provider that answers from a function of the history (one step per chat call)."""
    kind = "scripted"

    def __init__(self, steps):
        self.steps, self.seen_tools = list(steps), []

    def chat(self, system, history, tools):
        self.seen_tools.append({t["name"] for t in tools})
        return self.steps.pop(0)(history)


def last_result(history):
    return json.loads(history[-1]["results"][-1]["content"].split("\n")[0])


class AgentTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("pcbai.kicad.files.run", return_value=CompletedProcess([], 0, "", ""))
        patcher.start()
        self.addCleanup(patcher.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.project = make_project(root / "project")
        (root / "state").mkdir()
        self.engine = Engine([self.project], root / "state")
        self.session = next(iter(self.engine.sessions.entries))
        self.base = self.engine.sessions.get(self.session).target("Test.kicad_sch")
        self.agent = model.Agent(EngineClient(self.engine), self.session, "Test.kicad_pro")
        self.events = []
        self.emit = lambda kind, text: self.events.append((kind, str(text)))

    def preview_then_apply(self):
        preview = dict(self.base, mode="preview", reference="R1", value="4k7")
        return [
            lambda h: model.Reply("", [model.ToolCall("c1", "set_value", preview)]),
            lambda h: model.Reply("", [model.ToolCall("c2", "set_value", dict(
                self.base, mode="apply", candidate_id=last_result(h)["candidate_id"]))]),
            lambda h: model.Reply("R1 değeri 4k7 oldu." if last_result(h)["ok"] else "Uygulanmadı."),
        ]

    def schematic(self):
        return (self.project.parent / "Test.kicad_sch").read_bytes()

    def test_plan_mode_offers_and_runs_no_writer(self):
        provider = Scripted([lambda h: model.Reply("", [model.ToolCall("c1", "set_value", dict(
            self.base, mode="preview", reference="R1", value="1k"))]), lambda h: model.Reply(last_result(h)["summary"])])
        self.agent.run(provider, {}, "R1'i 1k yap", mode="plan", emit=self.emit)
        writers = {t["name"] for t in self.engine.definitions if t["annotations"]["destructiveHint"]}
        self.assertFalse(provider.seen_tools[0] & writers)
        self.assertIn("pcbai_status", provider.seen_tools[0])
        self.assertIn("Planla modunda kullanılamaz", self.events[-1][1])

    def test_act_mode_preview_free_apply_needs_approval(self):
        before = self.schematic()
        asked = []
        self.agent.run(Scripted(self.preview_then_apply()), {}, "R5 değerini oku, R1'i 4k7 yap", mode="act",
                       approve=lambda call, text: asked.append(text) or False, emit=self.emit)
        self.assertEqual(len(asked), 1)  # preview ran without asking; apply asked once
        self.assertIn("mode = \"apply\"", asked[0])
        self.assertIn("Önizleme özeti", asked[0])
        self.assertEqual(self.schematic(), before)
        self.assertEqual(self.events[-1], ("assistant", "Uygulanmadı."))
        self.agent.reset()
        self.agent.run(Scripted(self.preview_then_apply()), {}, "R1'i 4k7 yap", mode="act",
                       approve=lambda call, text: True, emit=self.emit)
        self.assertIn(b'"4k7"', self.schematic())
        self.assertEqual(self.events[-1], ("assistant", "R1 değeri 4k7 oldu."))
        events = self.engine.recent_events()
        self.assertTrue(all(e["client"] == "builtin" for e in events))
        self.assertTrue(any(e["tool"] == "set_value" and e["change_id"] for e in events))

    def test_third_identical_failure_stops(self):
        bad = model.ToolCall("x", "net_info", {"session": self.session, "document": "nope.kicad_pcb",
                                               "revision": "0" * 64, "net": "GND"})
        provider = Scripted([lambda h: model.Reply("", [bad])] * 5)
        self.agent.run(provider, {}, "GND", mode="plan", emit=self.emit)
        self.assertEqual(len(provider.steps), 2)
        self.assertIn("3 kez hata verdi", self.events[-1][1])
        self.assertIn("zaten denedin", self.agent.history[-1]["results"][0]["content"])

    def test_unknown_tool_and_history_stays_valid(self):
        provider = Scripted([lambda h: model.Reply("", [model.ToolCall("a", "rm_rf", {})]), lambda h: model.Reply("tamam")])
        self.agent.run(provider, {}, "x", mode="act", emit=self.emit)
        tool_turn = self.agent.history[2]
        self.assertEqual(tool_turn["results"][0]["id"], "a")
        self.assertIn("Bilinmeyen araç", tool_turn["results"][0]["content"])

    def test_small_mode_tool_set(self):
        tools = self.engine.definitions
        small = {t["name"] for t in model.select_tools(tools, "act", True, ["kartta autoroute önizle"])}
        self.assertTrue({"pcbai_status", "set_value", "check"} <= small)
        self.assertIn("autoroute", small)
        self.assertNotIn("export_fab", small)
        self.assertLess(len(small), len(tools))


class FakeServer(BaseHTTPRequestHandler):
    replies, requests = [], []

    def log_message(self, *_):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeServer.requests.append((self.path, dict(self.headers), body))
        data = json.dumps(FakeServer.replies.pop(0)).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class HttpProviderTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeServer)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        FakeServer.requests.clear()
        tool = {"name": "get_markers", "description": "d", "inputSchema": {"type": "object"}}
        self.tools = [tool]
        self.history = [{"role": "user", "text": "işaretler?"},
                        {"role": "assistant", "text": "", "tool_calls": [model.ToolCall("t1", "get_markers", {"session": "s"})]},
                        {"role": "tool", "results": [{"id": "t1", "name": "get_markers", "content": "{}", "is_error": False}]}]

    def test_ollama_native_chat(self):
        FakeServer.replies = [{"message": {"content": "<think>x</think>Bitti", "tool_calls": [
            {"function": {"name": "get_markers", "arguments": {"session": "s"}}}]}, "done_reason": "stop"}]
        reply = model.Ollama(dict(kind="ollama", base_url=self.url + "/v1", model="qwen3:8b")).chat("sys", self.history, self.tools)
        path, _headers, body = FakeServer.requests[0]
        self.assertEqual(path, "/api/chat")
        self.assertEqual(body["options"]["num_ctx"], model.NUM_CTX)
        self.assertEqual(body["messages"][2]["tool_calls"][0]["function"]["arguments"], {"session": "s"})
        self.assertEqual(body["messages"][3], {"role": "tool", "content": "{}", "tool_name": "get_markers"})
        self.assertEqual((reply.text, reply.tool_calls[0].name), ("Bitti", "get_markers"))

    def test_openai_compatible_key_from_env_only(self):
        FakeServer.replies = [{"choices": [{"message": {"content": "ok", "tool_calls": [
            {"id": "c9", "function": {"name": "get_markers", "arguments": "{\"session\": \"s\"}"}}]},
            "finish_reason": "tool_calls"}]}]
        profile = dict(kind="openai", base_url=self.url + "/v1", model="m", key_env="PCBAI_TEST_KEY")
        with mock.patch.dict(os.environ, {"PCBAI_TEST_KEY": SECRET}):
            reply = model.OpenAICompatible(profile).chat("sys", self.history, self.tools)
            self.assertEqual(model.redact(f"hata {SECRET}", profile), "hata ***")
        path, headers, body = FakeServer.requests[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer " + SECRET)
        self.assertNotIn(SECRET, json.dumps(body))
        self.assertEqual(reply.tool_calls[0].args, {"session": "s"})

    def test_unreachable_server_message(self):
        profile = dict(kind="ollama", base_url="http://127.0.0.1:9", model="qwen3:8b")
        with self.assertRaisesRegex(model.ProviderError, "Ollama açık mı"):
            model.Ollama(profile).chat("s", [{"role": "user", "text": "x"}], [])


class ClaudeProviderTests(unittest.TestCase):
    def fake_anthropic(self, response):
        calls = []

        class Errors(Exception):
            def __init__(self, message="", status_code=0):
                super().__init__(message)
                self.message, self.status_code = message, status_code

        class Client:
            def __init__(self, api_key, timeout):
                calls.append(("init", api_key))
                self.messages = types.SimpleNamespace(create=lambda **kw: calls.append(("create", kw)) or response)
                self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(
                    create=lambda **kw: calls.append(("beta", kw)) or response))
        module = types.SimpleNamespace(Anthropic=Client, AuthenticationError=type("A", (Errors,), {}),
                                       RateLimitError=type("R", (Errors,), {}), APIStatusError=type("S", (Errors,), {}),
                                       APIConnectionError=type("C", (Errors,), {}))
        return module, calls

    def test_claude_request_shape_and_raw_replay(self):
        block = lambda **kw: types.SimpleNamespace(**kw)  # noqa: E731
        response = types.SimpleNamespace(stop_reason="tool_use", content=[
            block(type="thinking", thinking=""), block(type="text", text="Bakıyorum"),
            block(type="tool_use", id="tu1", name="get_markers", input={"session": "s"})])
        module, calls = self.fake_anthropic(response)
        profile = dict(kind="anthropic", model=model.DEFAULT_CLAUDE, key_env="PCBAI_TEST_KEY")
        with mock.patch.dict(sys.modules, {"anthropic": module}), mock.patch.dict(os.environ, {"PCBAI_TEST_KEY": SECRET}):
            provider = model.Claude(profile)
            reply = provider.chat("sys", [{"role": "user", "text": "x"}],
                                  [{"name": "get_markers", "description": "d", "inputSchema": {"type": "object"}}])
            history = [{"role": "user", "text": "x"},
                       {"role": "assistant", "text": reply.text, "tool_calls": reply.tool_calls, "raw": reply.raw,
                        "raw_kind": "anthropic"},
                       {"role": "tool", "results": [{"id": "tu1", "name": "get_markers", "content": "{}", "is_error": False}]}]
            replay = provider.messages(history)
        kind, kwargs = calls[1]
        self.assertEqual(kind, "beta")
        self.assertEqual(kwargs["model"], "claude-opus-5-5")
        self.assertEqual(kwargs["fallbacks"], "default")
        self.assertEqual(kwargs["betas"], ["server-side-fallback-2026-07-01"])
        self.assertNotIn("thinking", kwargs)
        self.assertNotIn("tool_choice", kwargs)
        self.assertEqual(kwargs["tools"][0]["input_schema"], {"type": "object"})
        self.assertEqual((reply.text, reply.tool_calls[0].id), ("Bakıyorum", "tu1"))
        self.assertIs(replay[1]["content"], response.content)  # thinking blocks go back unchanged
        self.assertEqual(replay[2]["content"][0]["tool_use_id"], "tu1")
        self.assertNotIn(SECRET, json.dumps(kwargs, default=str))

    def test_missing_sdk_and_missing_key(self):
        profile = dict(kind="anthropic", model=model.DEFAULT_CLAUDE, key_env="PCBAI_TEST_KEY")
        with mock.patch.dict(sys.modules, {"anthropic": None}):
            self.assertFalse(model.sdk_installed())
            with self.assertRaises(model.MissingPackage):
                model.Claude(profile).client()
        module, _ = self.fake_anthropic(None)
        with mock.patch.dict(sys.modules, {"anthropic": module}), mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PCBAI_TEST_KEY", None)
            with self.assertRaisesRegex(model.ProviderError, "PCBAI_TEST_KEY ortam değişkeni"):
                model.Claude(profile).client()

    def test_refusal_is_reported(self):
        response = types.SimpleNamespace(stop_reason="refusal", content=[],
                                         stop_details=types.SimpleNamespace(explanation="politika"))
        module, _ = self.fake_anthropic(response)
        profile = dict(kind="anthropic", model="claude-haiku-5-5", key_env="PCBAI_TEST_KEY")
        with mock.patch.dict(sys.modules, {"anthropic": module}), mock.patch.dict(os.environ, {"PCBAI_TEST_KEY": SECRET}):
            reply = model.Claude(profile).chat("s", [{"role": "user", "text": "x"}], [])
        self.assertEqual(reply.stop_reason, "refusal")
        self.assertIn("politika", reply.text)

    def test_install_uses_argv_and_timeout(self):
        seen = []
        model.install_sdk(run=lambda argv, **kw: seen.append((argv, kw)) or CompletedProcess(argv, 0, "", ""))
        argv, kw = seen[0]
        self.assertEqual(argv[1:], ["-m", "pip", "install", "--disable-pip-version-check", "anthropic"])
        self.assertFalse(kw["shell"])
        self.assertEqual(kw["timeout"], 600)
        with self.assertRaisesRegex(model.ProviderError, "kurulamadı"):
            model.install_sdk(run=lambda argv, **kw: CompletedProcess(argv, 1, "", "no network"))


class KeyNeverStoredTests(unittest.TestCase):
    def test_profile_and_settings_hold_variable_name_only(self):
        for profile in model.PROVIDERS:
            self.assertNotIn("api_key", profile)
        claude = next(p for p in model.PROVIDERS if p["kind"] == "anthropic")
        self.assertEqual((claude["model"], claude["key_env"]), ("claude-opus-5-5", "ANTHROPIC_API_KEY"))
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": SECRET}):
            self.assertEqual(model.api_key(claude), SECRET)
            self.assertNotIn(SECRET, json.dumps(model.PROVIDERS))
            self.assertEqual(model.redact(Exception("x " + SECRET), claude), "x ***")


if __name__ == "__main__":
    unittest.main()
