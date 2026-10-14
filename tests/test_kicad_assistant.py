"""AJ-4: PcbAi Asistan logic without wx — catalogue/detection, KiCad selection rows, prompt, delivery, single instance."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from kicad_plugin import assistant_core as core


class Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FootprintInstance(Obj):
    pass


class Track(Obj):
    pass


class Pad(Obj):
    pass


class CatalogTests(unittest.TestCase):
    def test_detection_marks_missing_rows(self):
        found = {"claude": Path("C:/u/.local/bin/claude.exe")}
        rows = core.detect(find=lambda p: found.get(p), extensions=lambda: {"anthropic.claude-code"})
        by = {r["id"]: r for r in rows}
        self.assertEqual([r["id"] for r in rows], ["vscode", "claude-cli", "codex-cli", "builtin", "clipboard"])
        self.assertTrue(by["claude-cli"]["available"])
        self.assertFalse(by["codex-cli"]["available"])
        self.assertEqual(by["codex-cli"]["reason"], "kurulu değil")
        self.assertFalse(by["vscode"]["available"])
        self.assertTrue(by["vscode"]["claude_fallback"])
        self.assertTrue(by["clipboard"]["available"])
        self.assertEqual(core.default_row(rows, "codex-cli")["id"], "claude-cli")
        rows = core.detect(find=lambda p: None, extensions=lambda: {"taymur.pcbai-vscode"})
        self.assertEqual(core.default_row(rows)["id"], "vscode")

    def test_only_exe_is_accepted(self):
        exists = lambda path: True  # noqa: E731
        with mock.patch.object(core, "known_paths", return_value=[]):
            self.assertIsNone(core.find_program("claude", which=lambda n: "C:/npm/claude.cmd", exists=exists))
            self.assertEqual(core.find_program("codex", which=lambda n: "C:/bin/codex.exe" if n == "codex.exe" else None,
                                               exists=exists), Path("C:/bin/codex.exe"))

    def test_vscode_extensions_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "extensions.json"
            path.write_text(json.dumps([{"identifier": {"id": "Taymur.PcbAi-VSCode"}}, {"bad": 1}]), encoding="utf-8")
            self.assertEqual(core.vscode_extensions(path), {"taymur.pcbai-vscode"})
            path.write_text("{bozuk", encoding="utf-8")
            self.assertEqual(core.vscode_extensions(path), set())


class SelectionTests(unittest.TestCase):
    def test_rows_from_kipy_like_objects(self):
        text = lambda v: Obj(text=Obj(value=v))  # noqa: E731
        items = [FootprintInstance(reference_field=text("R5"), value_field=text("10k"), layer=3,
                                   position=Obj(x=12_500_000, y=-3_000_000)),
                 Track(net=Obj(name="VBUS"), layer=4, start=Obj(x=1_234_567, y=0)),
                 Pad(number="2", net=Obj(name="GND"), position=Obj(x=0, y=0))]
        with mock.patch.object(core, "_layer", side_effect=lambda item: {3: "F.Cu", 4: "B.Cu"}.get(getattr(item, "layer", None))):
            rows = core.selection_rows(items)
        self.assertEqual(rows[0], dict(type="footprint", reference="R5", value="10k", layer="F.Cu", x_mm=12.5, y_mm=-3.0))
        self.assertEqual(rows[1], dict(type="track", net="VBUS", layer="B.Cu", x_mm=1.2346, y_mm=0.0))
        self.assertEqual(rows[2]["reference"], "2")
        self.assertEqual(core.selection_summary(rows), "3 öğe: R5, net VBUS, 2")
        self.assertEqual(core.selection_summary([]), "seçim yok")


class PromptDeliveryTests(unittest.TestCase):
    def test_compose_uses_service_endpoint(self):
        client = mock.Mock()
        client.request.return_value = {"ok": True, "prompt": "P"}
        self.assertEqual(core.compose(client, "s-1", "iste", [1], [{"type": "footprint"}]), "P")
        client.request.assert_called_once_with("POST", "/agent/prompt", {"session": "s-1", "request": "iste",
                                               "marker_ids": [1], "selection": [{"type": "footprint"}]})
        client.request.return_value = {"ok": False, "error": {"message": "İstek yazın"}}
        with self.assertRaisesRegex(RuntimeError, "İstek yazın"):
            core.compose(client, "s-1", "", [], [])

    def test_cli_delivery_is_argv_without_shell(self):
        calls = []
        row = dict(id="claude-cli", kind="cli", label="Claude Code (terminal) — doğrudan gönderilir",
                   path=Path("C:/bin/claude.exe"))
        with tempfile.TemporaryDirectory() as root:
            outcome, text = core.deliver(row, 'satır 1\n"tırnak" -x', root,
                                         popen=lambda argv, **kw: calls.append((argv, kw)))
            self.assertEqual(outcome, "sent")
            argv, kw = calls[0]
            self.assertEqual(argv, [str(Path("C:/bin/claude.exe")), 'satır 1 "tırnak" -x'])
            self.assertFalse(kw["shell"])
            self.assertEqual(kw["cwd"], root)
            long = "a" * (core.CLI_MAX + 10)
            core.deliver(row, long, root, popen=lambda argv, **kw: calls.append((argv, kw)))
            files = list((Path(root) / ".pcbai-state" / "prompts").glob("*.md"))
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].read_text(encoding="utf-8"), long)
            self.assertIn(str(files[0]), calls[1][0][1])
        with self.assertRaises(RuntimeError):
            core.deliver(dict(row, path=Path("C:/npm/claude.cmd")), "x", ".", popen=lambda *a, **k: None)

    def test_old_prompt_files_removed(self):
        with tempfile.TemporaryDirectory() as root:
            first = core.prompt_file(root, "eski", now=lambda: 0)
            import os
            os.utime(first, (0, 0))
            core.prompt_file(root, "yeni", now=lambda: core.PROMPT_LIFETIME + 10)
            self.assertFalse(first.exists())

    def test_handoff_url_carries_only_id(self):
        opened = []
        row = dict(id="vscode", kind="handoff", label="VS Code'daki ajan — x")
        outcome, _ = core.deliver(row, "gizli istem", ".", handoff=lambda p: "0f8fad5b-d9cb-469f-a165-70867728950e",
                                  open_uri=opened.append)
        self.assertEqual(outcome, "handoff")
        self.assertEqual(opened, ["vscode://taymur.pcbai-vscode/handoff?id=0f8fad5b-d9cb-469f-a165-70867728950e"])
        self.assertEqual(core.deliver(dict(id="clipboard", kind="clipboard", label="x"), "p", ".")[0], "clipboard")

    def test_check_lines_and_activity(self):
        lines = core.check_lines({"ok": True, "verified": "checks_incomplete", "summary": "erc=ran, drc=failed",
                                  "warnings": ["w"], "active_findings": [{"severity": "error", "description": "d"}] * 10,
                                  "waived": [{}], "evidence_id": "e1",
                                  "checks_run": [{"check_id": "drc", "status": "failed", "reason": "rule_ignored_in_project"}],
                                  "expired_waivers": [{"finding_id": "drc:x:aaaaaaaaaaaa"}]})
        self.assertIn("  drc: failed (rule_ignored_in_project)", lines)
        self.assertIn("  1 süresi dolmuş muafiyet: drc:x:aaaaaaaaaaaa", lines)
        self.assertTrue(any(line.startswith("Denetim eksik") for line in lines))
        self.assertIn("checks_incomplete: erc=ran, drc=failed  (kanıt e1)", lines)
        self.assertIn("  … 2 bulgu daha (VS Code: PcbAi → ERC ve DRC çalıştır)", lines)
        self.assertIn("  1 bulgu muafiyetli", lines)
        self.assertEqual(core.check_lines({"ok": False, "summary": "x"}), ["Çalışmadı: x"])
        self.assertIn("PCB editörünü kapatın", core.guidance({"outcome": "blocked"}))
        self.assertIsNone(core.guidance({"outcome": "ok"}))
        self.assertIn("mcp:claude-code  set_value  ok · c1",
                      core.event_line({"time": 0, "client": "mcp:claude-code", "tool": "set_value", "outcome": "ok",
                                       "change_id": "c1"}))

    def test_guidance_matches_service_text(self):
        from pcbai.service.events import guidance
        for event in [{"outcome": "blocked"}, {"outcome": "ok", "change_id": "c"}, {"outcome": "ok"}]:
            self.assertEqual(core.guidance(event), guidance(event))


class SingleInstanceTests(unittest.TestCase):
    def test_second_start_raises_first_window(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "assistant.lock"
            self.assertFalse(core.signal_existing(lock))
            listener, token = core.claim(lock)
            raised = threading.Event()
            thread = threading.Thread(target=core.accept_raise, args=(listener, token, lambda _c: raised.set()), daemon=True)
            thread.start()
            self.assertTrue(core.signal_existing(lock))
            self.assertTrue(raised.wait(2))
            info = json.loads(lock.read_text(encoding="utf-8"))
            lock.write_text(json.dumps(dict(info, token="yanlış")), encoding="utf-8")
            self.assertFalse(core.signal_existing(lock))
            lock.write_text(json.dumps(info), encoding="utf-8")
            listener.close()
            thread.join(2)
            time.sleep(0.05)
            core.release(lock)
            self.assertFalse(lock.exists())
            self.assertFalse(core.signal_existing(lock))

    def test_marker_command_is_passed_to_window(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "assistant.lock"
            listener, token = core.claim(lock)
            commands = []
            thread = threading.Thread(target=core.accept_raise, args=(listener, token, commands.append), daemon=True)
            thread.start()
            self.assertTrue(core.signal_existing(lock, "marker"))
            self.assertTrue(core.signal_existing(lock))
            self.assertFalse(core.signal_existing(lock, "delete"))
            listener.close()
            thread.join(2)
            self.assertEqual(commands, ["marker", "raise"])
            core.release(lock)


class MarkerTests(unittest.TestCase):
    """Plan IM: KiCad selection / schematic symbol → marker through the service view endpoint."""

    def test_pcb_marker_anchors_footprint_else_point(self):
        rows = [dict(type="track", net="GND", layer="F.Cu", x_mm=1.0, y_mm=2.0, uuid="t"),
                dict(type="footprint", reference="R1", layer="F.Cu", x_mm=10.0, y_mm=20.0, uuid="fp")]
        self.assertEqual(core.pcb_marker(rows, "not"), dict(
            kind="item", space="pcb", points_mm=[[10.0, 20.0]], note="not", layer="F.Cu",
            anchor=dict(type="footprint", uuid="fp")))
        self.assertEqual(core.pcb_marker(rows[:1], "n")["kind"], "point")
        self.assertIsNone(core.pcb_marker([dict(type="zone")], "n"))
        self.assertIsNone(core.pcb_marker([], "n"))

    def test_selection_rows_keep_kicad_uuid(self):
        fp = FootprintInstance(id=Obj(value="abc"), position=Obj(x=1_000_000, y=2_000_000))
        self.assertEqual(core.selection_rows([fp])[0]["uuid"], "abc")

    def test_schematic_helpers(self):
        with tempfile.TemporaryDirectory() as temp:
            sch = Path(temp) / "a.kicad_sch"
            sch.write_text('(kicad_sch (version 1) (uuid "8E1C2C9A-0000-4000-8000-000000000001") (paper "A4"))')
            self.assertEqual(core.root_sheet(sch), "/8e1c2c9a-0000-4000-8000-000000000001")
            sch.write_text("(kicad_sch)")
            with self.assertRaises(RuntimeError):
                core.root_sheet(sch)
        scene = {"items": [dict(type="symbol", uuid="b", reference="R10", at=[1, 2]),
                           dict(type="symbol", uuid="a", reference="R2", at=[3, 4]),
                           dict(type="symbol", uuid="p", reference="#PWR1", power=True, at=[0, 0]),
                           dict(type="pin", uuid="x", reference="R2")]}
        self.assertEqual([s["reference"] for s in core.sch_symbols(scene)], ["R2", "R10"])
        self.assertEqual(core.sch_marker(scene["items"][1], "/r", "n"), dict(
            kind="item", space="sch", points_mm=[[3, 4]], note="n", sheet="/r", anchor=dict(type="symbol", uuid="a")))

    def test_save_marker_round_trip_through_engine(self):
        from pcbai.tools.engine import Engine
        from tests.helpers import make_project
        from tests.test_views import GEOMETRY

        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp) / "project")
            board = project.with_suffix(".kicad_pcb")
            board.write_bytes(GEOMETRY)
            (Path(temp) / "state").mkdir()
            engine = Engine([project], Path(temp) / "state")
            session = next(iter(engine.sessions.entries.values()))

            class Client:
                paths = []

                def request(self, method, path, body):
                    self.paths.append(path)
                    return engine.call(body["name"], body["arguments"], source="view" if path == "/view/call" else "tool")

            client = Client()
            marker = core.pcb_marker([dict(type="footprint", x_mm=10, y_mm=20, layer="F.Cu", uuid="front")], "0603 yap")
            saved = core.save_marker(client, session.id, board.name, marker)
            self.assertEqual((saved["n"], saved["note"], saved["anchor"]["uuid"]), (1, "0603 yap", "front"))
            self.assertIn("/view/call", client.paths)
            core.save_marker(client, session.id, None, n=1, note="0805 yap")
            stored = engine.call("get_markers", {"session": session.id})["markers"]
            self.assertEqual([(m["n"], m["note"], m["kind"]) for m in stored], [(1, "0805 yap", "item")])
            with self.assertRaises(core.MarkerError) as caught:
                core.save_marker(client, session.id, board.name, dict(marker, anchor=dict(type="footprint", uuid="yok")))
            self.assertEqual(caught.exception.code, "invalid_anchor")
            with self.assertRaises(RuntimeError):
                core.save_marker(client, session.id, None, n=9, note="x")


if __name__ == "__main__":
    unittest.main()
