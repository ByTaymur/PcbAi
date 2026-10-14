"""PcbAi Asistan: the wx window started by the KiCad button (plan AJ-4). Runs as its own process so KiCad never waits.

    pythonw assistant_window.py --parent-pid <KiCad pid>

Single instance (lock + loopback "raise" socket, AJ-S1), closes when KiCad exits, polls the KiCad selection and the
service activity log. Logic lives in assistant_core.py; this file only draws it.
"""
import argparse
import ctypes
import json
import os
import sys
import threading
import traceback
from pathlib import Path

import wx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import assistant_core as core  # noqa: E402
import assistant_model as model  # noqa: E402
from pcbai_kicad import client_for, current_project, pcbai_root, session_for  # noqa: E402

SETTINGS = Path(os.environ.get("APPDATA", Path.home())) / "PcbAi" / "assistant.json"
LOCK = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PcbAi" / "assistant.lock"
SELECTION_MS = 700
EVENTS_MS = 1500


def load_settings():
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


class AssistantFrame(wx.Frame):
    def __init__(self, parent_pid=None):
        super().__init__(None, title="PcbAi Asistan", size=(640, 820),
                         style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.settings = load_settings()
        self.client = self.session = self.project = None
        self.board = None
        self.selection = []
        self.markers = []
        self.events_since = None
        self.pending_handoff = None
        self.agent_loop = None
        self.running = False
        self.stopping = threading.Event()
        self.rows = core.detect()
        self.build()
        self.provider.SetSelection(next((i for i, p in enumerate(model.PROVIDERS)
                                         if p["id"] == self.settings.get("provider")), 0))
        self.load_provider()
        self.show_builtin()
        self.connect()
        self.timers = []
        self.every(SELECTION_MS, self.poll_selection)
        self.every(EVENTS_MS, self.poll_events)
        if parent_pid:
            self.watch_parent(parent_pid)

    # --- layout -------------------------------------------------------------------------------------------------
    def build(self):
        panel = wx.Panel(self)
        grid = wx.BoxSizer(wx.VERTICAL)
        top = wx.BoxSizer(wx.HORIZONTAL)
        self.project_label = wx.StaticText(panel, label="Proje: —")
        self.keep_top = wx.CheckBox(panel, label="üstte tut")
        self.keep_top.SetValue(True)
        self.keep_top.Bind(wx.EVT_CHECKBOX, self.on_keep_top)
        top.Add(self.project_label, 1, wx.ALIGN_CENTER_VERTICAL)
        top.Add(self.keep_top, 0)
        grid.Add(top, 0, wx.EXPAND | wx.ALL, 6)

        agent = wx.BoxSizer(wx.HORIZONTAL)
        agent.Add(wx.StaticText(panel, label="YAPAY ZEKÂ  Ajan"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        labels = [r["label"] + ("" if r["available"] else f" ({r['reason']})") for r in self.rows]
        self.agent = wx.Choice(panel, choices=labels)
        chosen = core.default_row(self.rows, self.settings.get("agent"))
        self.agent.SetSelection(self.rows.index(chosen))
        self.agent.Bind(wx.EVT_CHOICE, self.on_agent)
        agent.Add(self.agent, 1)
        grid.Add(agent, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        grid.Add(self.build_builtin(panel), 0, wx.EXPAND | wx.ALL, 6)

        grid.Add(wx.StaticText(panel, label="İsteğin"), 0, wx.LEFT | wx.TOP, 6)
        self.request = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 90))
        self.request.SetMaxLength(8000)
        grid.Add(self.request, 0, wx.EXPAND | wx.ALL, 6)

        self.use_selection = wx.CheckBox(panel, label="KiCad seçimini ekle (seçim yok)")
        self.use_selection.SetValue(True)
        grid.Add(self.use_selection, 0, wx.LEFT | wx.RIGHT, 6)

        marks = wx.BoxSizer(wx.HORIZONTAL)
        marks.Add(wx.StaticText(panel, label="İşaretler"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        reload = wx.Button(panel, label="yenile", style=wx.BU_EXACTFIT)
        reload.Bind(wx.EVT_BUTTON, lambda _e: self.load_markers())
        marks.Add(reload, 0)
        grid.Add(marks, 0, wx.LEFT | wx.TOP, 6)
        self.marker_list = wx.CheckListBox(panel, size=(-1, 80))
        self.marker_list.Bind(wx.EVT_LISTBOX, self.on_marker_pick)
        grid.Add(self.marker_list, 0, wx.EXPAND | wx.ALL, 6)
        grid.Add(self.build_marker(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in [("Ajana gönder", self.on_send), ("Kopyala", self.on_copy),
                               ("ERC/DRC", self.on_check), ("VS Code'da aç", self.on_vscode)]:
            button = wx.Button(panel, label=label)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(button, 0, wx.RIGHT, 4)
        grid.Add(buttons, 0, wx.ALL, 6)

        self.preview_pane = wx.CollapsiblePane(panel, label="Oluşan istem")
        self.preview = wx.TextCtrl(self.preview_pane.GetPane(), style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 110))
        pane = wx.BoxSizer(wx.VERTICAL)
        pane.Add(self.preview, 1, wx.EXPAND)
        self.preview_pane.GetPane().SetSizer(pane)
        self.preview_pane.Expand()  # terminal agents start at once: the prompt is visible by default
        grid.Add(self.preview_pane, 0, wx.EXPAND | wx.ALL, 6)

        grid.Add(wx.StaticText(panel, label="Ajan etkinliği"), 0, wx.LEFT, 6)
        self.activity = wx.ListBox(panel, size=(-1, 100))
        grid.Add(self.activity, 1, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="Durum: hazır")
        grid.Add(self.status, 0, wx.EXPAND | wx.ALL, 6)
        panel.SetSizer(grid)

    def every(self, ms, fn):
        timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda _e: self.safe(fn), timer)
        timer.Start(ms)
        self.timers.append(timer)

    def safe(self, fn, *args):
        try:
            fn(*args)
        except Exception as exc:  # every failure is shown in the window, never swallowed silently
            self.say(f"Hata: {exc}", error=True)
            print(traceback.format_exc(), file=sys.stderr)

    def say(self, text, error=False):
        self.status.SetLabel("Durum: " + text)
        self.status.SetForegroundColour(wx.Colour(200, 30, 30) if error else wx.NullColour)
        self.status.Wrap(self.GetClientSize().width - 20)
        self.Layout()

    # --- service and KiCad -------------------------------------------------------------------------------------
    def connect(self):
        try:
            self.project, _board = current_project()
            self.client = client_for(self.project)
            self.session = session_for(self.client, self.project)
            from pcbai import __version__
            self.project_label.SetLabel(f"Proje: {self.project.name}  ● servis  PcbAi {__version__}")
            self.load_markers()
        except Exception as exc:
            hint = (" KiCad eklenti bağımlılıkları (kicad-python) kurulamadı; ağ erişimini kontrol edin."
                    if isinstance(exc, ModuleNotFoundError) and (exc.name or "").startswith("kipy") else "")
            self.project_label.SetLabel("Proje: bağlanamadı")
            self.say(f"{exc}{hint}", error=True)

    def load_markers(self, only=None):
        """Open markers into the list, all checked; ``only``: check just that marker number."""
        if not self.client:
            return
        response = self.client.request("POST", "/call", {"name": "get_markers",
                                                         "arguments": {"session": self.session["id"]}})
        if not response.get("ok"):
            raise RuntimeError(response.get("summary") or "İşaretler okunamadı")
        self.markers = [m for m in response.get("markers", []) if m.get("status") == "open"]
        self.marker_list.Set([f"#{m['n']} {m.get('document', '')}: {m.get('note', '')}"[:120] for m in self.markers])
        for index, marker in enumerate(self.markers):
            self.marker_list.Check(index, only is None or marker["n"] == only)

    def poll_selection(self):
        try:
            if self.board is None:
                from kipy import KiCad
                self.board = KiCad(client_name="pcbai-assistant").get_board()
            self.selection = core.selection_rows(self.board.get_selection())
        except Exception:
            self.board, self.selection = None, []  # KiCad busy or editor closed: try again on the next tick
        self.use_selection.SetLabel(f"KiCad seçimini ekle ({core.selection_summary(self.selection)})")
        self.show_marker_target()

    def poll_events(self):
        if not self.client:
            return
        path = "/events" + (f"?since={self.events_since}" if self.events_since is not None else "")
        events = self.client.request("GET", path).get("events", [])
        for event in events:
            self.events_since = event["seq"]
            self.activity.Append(core.event_line(event))
            hint = core.guidance(event)
            if hint:
                self.say(hint)
        while self.activity.GetCount() > 50:
            self.activity.Delete(0)
        if self.pending_handoff:
            state = self.client.request("POST", "/handoff/status", {"id": self.pending_handoff})
            if state.get("ok") and state.get("outcome"):
                self.say(f"VS Code: {state.get('message') or state['outcome']}")
                self.pending_handoff = None

    # --- actions ------------------------------------------------------------------------------------------------
    def compose(self):
        if not self.client:
            raise RuntimeError("Servise bağlı değil")
        ids = [self.markers[i]["n"] for i in self.marker_list.GetCheckedItems()]
        selection = self.selection if self.use_selection.GetValue() else None
        prompt = core.compose(self.client, self.session["id"], self.request.GetValue(), ids, selection)
        self.preview.SetValue(prompt)
        return prompt

    def copy(self, text):
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(text))
            finally:
                wx.TheClipboard.Close()
            return True
        raise RuntimeError("Pano açılamadı")

    def handoff(self, prompt):
        response = self.client.request("POST", "/handoff/create", {"session": self.session["id"], "prompt": prompt})
        if not response.get("ok"):
            raise RuntimeError((response.get("error") or {}).get("message") or "Devir oluşturulamadı")
        self.pending_handoff = response["id"]
        return response["id"]

    def on_send(self, _event):
        def send():
            row = self.rows[self.agent.GetSelection()]
            if not row["available"]:
                raise RuntimeError(f"{row['label'].split(' — ')[0]}: {row['reason']}")
            if row["kind"] == "builtin":
                return self.ask_builtin()
            prompt = self.compose()
            if row["kind"] == "clipboard":
                self.copy(prompt)
            outcome, text = core.deliver(row, prompt, self.session["root"], handoff=self.handoff,
                                         open_uri=os.startfile)
            self.say(text)
        self.safe(send)

    def on_copy(self, _event):
        self.safe(lambda: (self.copy(self.compose()), self.say("İstem panoya kopyalandı.")))

    def on_vscode(self, _event):
        def open_folder():
            code = core.find_program("code")
            if not code:
                raise RuntimeError("VS Code bulunamadı")
            import subprocess
            subprocess.Popen([str(code), self.session["root"]], shell=False, close_fds=True)
            self.say("Proje klasörü VS Code'da açılıyor.")
        self.safe(open_folder)

    def on_check(self, _event):
        self.say("ERC/DRC çalışıyor…")

        def work():
            try:
                lines = run_checks(self.client, self.session, self.project)
                wx.CallAfter(self.show_check, lines)
            except Exception as exc:
                wx.CallAfter(self.say, f"ERC/DRC: {exc}", True)
        threading.Thread(target=work, daemon=True).start()

    def show_check(self, lines):
        self.preview.SetValue("\n".join(lines))
        self.preview_pane.Expand()
        self.Layout()
        self.say("ERC/DRC bitti; sonuç 'Oluşan istem' alanında.")

    def on_agent(self, _event):
        self.show_builtin()
        row = self.rows[self.agent.GetSelection()]
        self.settings["agent"] = row["id"]
        save_settings(self.settings)
        self.say(row["label"] if row["available"] else f"{row['label']} — {row['reason']}")

    def on_keep_top(self, _event):
        style = self.GetWindowStyle()
        self.SetWindowStyle(style | wx.STAY_ON_TOP if self.keep_top.GetValue() else style & ~wx.STAY_ON_TOP)

    # --- markers (plan IM) ----------------------------------------------------------------------------------------
    def build_marker(self, parent):
        box = wx.StaticBoxSizer(wx.VERTICAL, parent, "İşaret notu")
        owner = box.GetStaticBox()
        where = wx.BoxSizer(wx.HORIZONTAL)
        self.marker_space = wx.Choice(owner, choices=["PCB: KiCad seçimi", "Şematik: kaydedilmiş sayfa"])
        self.marker_space.SetSelection(0)
        self.marker_space.Bind(wx.EVT_CHOICE, self.on_marker_space)
        where.Add(self.marker_space, 0, wx.RIGHT, 4)
        self.sch_page = wx.Choice(owner, size=(150, -1))
        self.sch_page.Bind(wx.EVT_CHOICE, lambda _e: self.load_sch_page(self.sch_pages[self.sch_page.GetSelection()]))
        self.sch_symbol = wx.Choice(owner, size=(170, -1))
        self.sch_reload = wx.Button(owner, label="sayfaları oku", style=wx.BU_EXACTFIT)
        self.sch_reload.Bind(wx.EVT_BUTTON, lambda _e: self.load_sch_page(None))
        for widget in (self.sch_page, self.sch_symbol, self.sch_reload):
            where.Add(widget, 0, wx.RIGHT, 4)
        box.Add(where, 0, wx.EXPAND | wx.BOTTOM, 4)
        self.marker_target = wx.StaticText(owner, label="Hedef: KiCad'de bir öğe seçin")
        box.Add(self.marker_target, 0, wx.EXPAND | wx.BOTTOM, 4)
        self.marker_note = wx.TextCtrl(owner, style=wx.TE_MULTILINE, size=(-1, 60))
        self.marker_note.SetMaxLength(4096)
        self.marker_note.SetHint("Bu noktada ne yapılsın? (örn. R12'yi 0603'e çevir)")
        box.Add(self.marker_note, 0, wx.EXPAND | wx.BOTTOM, 4)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in [("İşaret koy", lambda _e: self.on_marker_add(False)),
                               ("Koy ve ajana gönder", lambda _e: self.on_marker_add(True)),
                               ("Notu kaydet", self.on_marker_note), ("Bu işareti uygula", self.on_marker_run)]:
            button = wx.Button(owner, label=label)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(button, 0, wx.RIGHT, 4)
        box.Add(buttons, 0)
        self.sch_pages, self.sch_rows, self.sch_sheet = [], [], None
        self.on_marker_space(None)
        return box

    def on_marker_space(self, _event):
        sch = self.marker_space.GetSelection() == 1
        for widget in (self.sch_page, self.sch_symbol, self.sch_reload):
            widget.Show(sch)
        self.show_marker_target()
        self.marker_space.GetParent().GetParent().Layout()  # the panel's sizer: hidden widgets give back room
        if sch and not self.sch_pages and self.client:
            self.load_sch_page(None)

    def show_marker_target(self):
        if self.marker_space.GetSelection() == 1:
            text = "Hedef: şematik bileşeni seçin (kaydedilmiş dosya; önce Ctrl+S)"
        else:
            marker = core.pcb_marker(self.selection, "")
            text = ("Hedef: KiCad'de bir öğe seçin" if marker is None else
                    f"Hedef: {core.selection_summary(self.selection)} · "
                    f"{'bileşene bağlı' if marker['kind'] == 'item' else 'nokta'} "
                    f"({marker['points_mm'][0][0]:.2f}, {marker['points_mm'][0][1]:.2f} mm)")
        if self.marker_target.GetLabel() != text:
            self.marker_target.SetLabel(text)

    def load_sch_page(self, page):
        """Read one saved schematic page instance (root when ``page`` is None) in the background."""
        if not self.client:
            return
        self.say("Şematik okunuyor…")
        root = Path(self.session["root"])
        document = Path(self.session["project"]).with_suffix(".kicad_sch").as_posix()
        session_id = self.session["id"]

        def work():
            try:
                sheet = page["instance"] if page else core.root_sheet(root / document)
                state = self.client.request("POST", "/call", {"name": "get_markers", "arguments": {"session": session_id}})
                response = self.client.request("POST", "/call", {"name": "scene_sch", "arguments": dict(
                    session=session_id, document=document, revision=state.get("revision", ""), sheet=sheet)})
                if not response.get("ok"):
                    raise RuntimeError((response.get("error") or {}).get("message") or response.get("summary")
                                       or "Şematik okunamadı")
                wx.CallAfter(self.show_sch, response, sheet)
            except Exception as exc:
                wx.CallAfter(self.say, f"Şematik: {exc}", True)
        threading.Thread(target=work, daemon=True).start()

    def show_sch(self, response, sheet):
        self.sch_pages = response.get("pages", [])
        self.sch_sheet = next((p for p in self.sch_pages if p["instance"] == sheet), None)
        self.sch_page.Set([f"{p.get('number', '')} {'/'.join(p.get('names') or []) or 'kök'}" for p in self.sch_pages])
        if self.sch_sheet:
            self.sch_page.SetSelection(self.sch_pages.index(self.sch_sheet))
        self.sch_rows = core.sch_symbols(response["scene"])
        self.sch_symbol.Set([f"{s['reference']} {s.get('value', '')}"[:40] for s in self.sch_rows])
        if self.sch_rows:
            self.sch_symbol.SetSelection(0)
        self.say(f"Şematik sayfası okundu: {len(self.sch_rows)} bileşen.")

    def marker_draft(self):
        note = self.marker_note.GetValue().strip()
        if not note:
            raise RuntimeError("Önce işaret notunu yazın")
        if self.marker_space.GetSelection() == 1:
            index = self.sch_symbol.GetSelection()
            if not self.sch_sheet or index == wx.NOT_FOUND:
                raise RuntimeError("Şematik bileşeni seçin ('sayfaları oku')")
            return self.sch_sheet["document"], core.sch_marker(self.sch_rows[index], self.sch_sheet["instance"], note)
        marker = core.pcb_marker(self.selection, note)
        if marker is None:
            raise RuntimeError("KiCad'de önce bir öğe seçin (bileşen, pad, yol…)")
        _project, board = current_project()
        return Path(os.path.relpath(board, self.session["root"])).as_posix(), marker

    def on_marker_add(self, send):
        def add():
            if not self.client:
                raise RuntimeError("Servise bağlı değil")
            document, marker = self.marker_draft()
            try:
                saved = core.save_marker(self.client, self.session["id"], document, marker)
            except core.MarkerError as exc:
                if exc.code != "invalid_anchor" or marker["kind"] != "item" or marker["space"] != "pcb":
                    raise
                # The footprint is not in the saved board yet: keep the point, drop the anchor.
                marker = {k: v for k, v in marker.items() if k != "anchor"}
                marker["kind"] = "point"
                saved = core.save_marker(self.client, self.session["id"], document, marker)
                self.say("Bileşen kayıtlı kartta yok; işaret nokta olarak kondu (kartı kaydedip yeniden koyabilirsiniz).")
            self.marker_note.SetValue("")
            self.load_markers(only=saved["n"] if send else None)
            self.say(f"#{saved['n']} işareti kondu.")
            if send:
                self.on_send(None)
        self.safe(add)

    def picked_marker(self):
        index = self.marker_list.GetSelection()
        if index == wx.NOT_FOUND:
            raise RuntimeError("Listeden bir işaret seçin")
        return self.markers[index]

    def on_marker_pick(self, _event):
        index = self.marker_list.GetSelection()
        if index != wx.NOT_FOUND:
            self.marker_note.SetValue(self.markers[index].get("note", ""))

    def on_marker_note(self, _event):
        def save():
            marker = self.picked_marker()
            note = self.marker_note.GetValue().strip()
            if not note:
                raise RuntimeError("Not boş olamaz")
            core.save_marker(self.client, self.session["id"], None, n=marker["n"], note=note)
            self.load_markers()
            self.say(f"#{marker['n']} notu kaydedildi.")
        self.safe(save)

    def on_marker_run(self, _event):
        def run():
            marker = self.picked_marker()
            self.load_markers(only=marker["n"])
            self.on_send(None)
        self.safe(run)

    def focus_marker(self):
        self.bring_front()
        self.marker_note.SetFocus()

    # --- built-in model (AJ-6) -----------------------------------------------------------------------------------
    def build_builtin(self, parent):
        self.builtin = wx.Panel(parent)
        form = wx.FlexGridSizer(cols=2, vgap=4, hgap=6)
        form.AddGrowableCol(1)
        self.provider = wx.Choice(self.builtin, choices=[p["label"] for p in model.PROVIDERS])
        self.provider.Bind(wx.EVT_CHOICE, lambda _e: self.load_provider())
        self.model_name = wx.TextCtrl(self.builtin)
        self.base_url = wx.TextCtrl(self.builtin)
        for label, widget in [("Sağlayıcı", self.provider), ("Model", self.model_name), ("Sunucu", self.base_url)]:
            form.Add(wx.StaticText(self.builtin, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            form.Add(widget, 1, wx.EXPAND)
        self.mode = wx.RadioBox(self.builtin, choices=["Planla (yalnız okuma)", "Uygula (yazanlar onaylı)"])
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.install = wx.Button(self.builtin, label="Paketi kur (anthropic)")
        self.install.Bind(wx.EVT_BUTTON, self.on_install)
        stop = wx.Button(self.builtin, label="Durdur")
        stop.Bind(wx.EVT_BUTTON, lambda _e: self.stopping.set())
        reset = wx.Button(self.builtin, label="Yeni sohbet")
        reset.Bind(wx.EVT_BUTTON, self.on_reset)
        self.provider_state = wx.StaticText(self.builtin, label="")
        for widget in (self.install, stop, reset):
            buttons.Add(widget, 0, wx.RIGHT, 4)
        buttons.Add(self.provider_state, 1, wx.ALIGN_CENTER_VERTICAL)
        self.chat = wx.TextCtrl(self.builtin, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(-1, 160))
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(form, 0, wx.EXPAND)
        outer.Add(self.mode, 0, wx.TOP, 4)
        outer.Add(buttons, 0, wx.EXPAND | wx.TOP, 4)
        outer.Add(self.chat, 1, wx.EXPAND | wx.TOP, 4)
        self.builtin.SetSizer(outer)
        return self.builtin

    def show_builtin(self):
        self.builtin.Show(self.rows[self.agent.GetSelection()]["kind"] == "builtin")
        self.Layout()

    def profile(self):
        """Provider settings; the key's environment variable name is stored, never the key."""
        base = dict(model.PROVIDERS[self.provider.GetSelection()])
        saved = self.settings.get("providers", {}).get(base["id"], {})
        base.update({k: v for k, v in saved.items() if k in ("model", "base_url", "num_ctx", "effort") and v})
        return base

    def load_provider(self):
        profile = self.profile()
        self.model_name.SetValue(profile.get("model") or "")
        self.base_url.SetValue(profile.get("base_url") or "")
        self.base_url.Enable(profile["kind"] != "anthropic")
        if profile["kind"] == "anthropic":
            ready = model.sdk_installed()
            key = bool(model.api_key(profile))
            self.install.Show(not ready)
            self.provider_state.SetLabel(("" if ready else "anthropic kurulu değil · ")
                                         + ("anahtar ortamda" if key else f"{profile['key_env']} tanımlı değil"))
        else:
            self.install.Hide()
            self.provider_state.SetLabel("küçük araç kümesi" if profile.get("small") else "")
        self.Layout()

    def save_provider(self):
        profile = self.profile()
        stored = self.settings.setdefault("providers", {}).setdefault(profile["id"], {})
        stored.update(model=self.model_name.GetValue().strip(), base_url=self.base_url.GetValue().strip())
        self.settings["provider"] = profile["id"]
        save_settings(self.settings)
        return dict(profile, **{k: v for k, v in stored.items() if v})

    def on_install(self, _event):
        if wx.MessageBox("Claude için 'anthropic' Python paketi KiCad eklenti ortamına kurulsun mu? (internet gerekir)",
                         "PcbAi Asistan", wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            return
        self.say("anthropic kuruluyor…")

        def work():
            try:
                model.install_sdk()
                wx.CallAfter(self.say, "anthropic kuruldu.")
            except Exception as exc:
                wx.CallAfter(self.say, str(exc), True)
            wx.CallAfter(self.load_provider)
        threading.Thread(target=work, daemon=True).start()

    def on_reset(self, _event):
        if self.running:
            self.say("Model çalışırken sohbet sıfırlanamaz; önce Durdur.", True)
            return
        if self.agent_loop:
            self.agent_loop.reset()
        self.chat.Clear()

    def log_chat(self, kind, text):
        prefix = {"assistant": "Model: ", "tool_call": "  → ", "tool_result": "  ← ", "info": "• ", "error": "! ",
                  "user": "Sen: "}.get(kind, "")
        self.chat.AppendText(prefix + str(text) + "\n")

    def approve(self, call, description):
        """Called from the model thread; asks on the GUI thread and waits for the answer."""
        answer, done = [False], threading.Event()

        def ask():
            try:
                dialog = wx.MessageDialog(self, "Model şu değişikliği uygulamak istiyor:\n\n" + description
                                          + "\n\nUygulansın mı?", "PcbAi Asistan — onay",
                                          wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
                answer[0] = dialog.ShowModal() == wx.ID_YES
                dialog.Destroy()
            finally:
                done.set()
        wx.CallAfter(ask)
        done.wait()
        return answer[0]

    def ask_builtin(self):
        if self.running:
            raise RuntimeError("Model hâlâ çalışıyor; bitmesini bekleyin ya da Durdur'a basın.")
        if not self.client:
            raise RuntimeError("Servise bağlı değil")
        prompt = self.compose()
        profile = self.save_provider()
        if self.agent_loop is None:
            import copy
            client = copy.copy(self.client)
            client.client_name = "builtin"  # the activity log names the built-in model, not the window
            self.agent_loop = model.Agent(client, self.session["id"], self.project.name)
        provider = model.make_provider(profile)
        mode = "plan" if self.mode.GetSelection() == 0 else "act"
        self.log_chat("user", self.request.GetValue().strip() or "(işaret/seçim isteği)")
        self.running = True
        self.stopping.clear()
        self.say(f"{profile['label']} çalışıyor ({'Planla' if mode == 'plan' else 'Uygula'})…")

        def emit(kind, text):
            wx.CallAfter(self.log_chat, kind, model.redact(text, profile))

        def work():
            try:
                self.agent_loop.run(provider, profile, prompt, mode=mode, approve=self.approve, emit=emit,
                                    should_stop=self.stopping.is_set)
            except Exception as exc:
                emit("error", exc)
            finally:
                self.running = False
                wx.CallAfter(self.say, "Model bitti.")
        threading.Thread(target=work, daemon=True).start()

    # --- process lifetime ---------------------------------------------------------------------------------------
    def watch_parent(self, pid):
        if os.name != "nt":
            return
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x00100000 | 0x1000, False, pid)  # SYNCHRONIZE | QUERY_LIMITED_INFORMATION
        if handle:
            self.every(250, lambda: kernel.WaitForSingleObject(handle, 0) != 0x102 and self.Close())

    def bring_front(self):
        if self.IsIconized():
            self.Iconize(False)
        self.Show()
        self.Raise()
        if os.name == "nt":
            ctypes.windll.user32.SetForegroundWindow(self.GetHandle())


def run_checks(client, session, _project):
    """ERC/DRC through the service's check tool, so ignored mandatory rules and waivers count as in VS Code."""
    response = client.request("POST", "/call", {"name": "check", "arguments": {"session": session["id"], "scope": "all"}})
    return core.check_lines(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-pid", type=int)
    parser.add_argument("--marker", action="store_true", help="focus the marker note (İşaret koy button)")
    args = parser.parse_args()
    if LOCK.exists() and core.signal_existing(LOCK, "marker" if args.marker else "raise"):
        return 0
    pcbai_root()  # fail early with the configuration hint
    listener, token = core.claim(LOCK)
    app = wx.App(False)
    frame = AssistantFrame(args.parent_pid)
    frame.Show()
    wx.CallAfter(frame.focus_marker if args.marker else frame.bring_front)

    def on_raise(command):
        wx.CallAfter(frame.focus_marker if command == "marker" else frame.bring_front)
    threading.Thread(target=core.accept_raise, args=(listener, token, on_raise), daemon=True).start()
    try:
        app.MainLoop()
    finally:
        listener.close()
        core.release(LOCK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
