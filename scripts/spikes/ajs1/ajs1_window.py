"""AJ-S1 deneme penceresi (ürün kodu değil; yalnız ölçüm).

    <eklenti venv>\\Scripts\\python.exe ajs1_window.py --log <dosya.jsonl> [--parent-pid N] [--poll-ms 500]
        [--auto-close-s S] [--state-dir D]

- Tek örnek: state-dir/ajs1.lock içinde port + belirteç; ikinci süreç 127.0.0.1'e "raise <belirteç>" yollar ve çıkar.
- Üst PID izleme: --parent-pid ölünce pencere kapanır (OpenProcess + WaitForSingleObject(0) yoklaması, 250 ms).
- --poll-ms: kipy ile get_selection yoklaması; her çağrının süresi ve süreç CPU zamanı loga yazılır.
- Ön plan: pencere gösterildikten sonra GetForegroundWindow == kendi HWND mi loga yazılır.
"""
import argparse
import ctypes
import json
import os
import secrets
import socket
import sys
import threading
import time
from pathlib import Path

import wx

K32 = ctypes.windll.kernel32
U32 = ctypes.windll.user32
SYNCHRONIZE = 0x00100000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class Log:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.t0 = time.perf_counter()

    def __call__(self, event, **data):
        row = {"t": round(time.perf_counter() - self.t0, 4), "wall": time.time(), "pid": os.getpid(), "event": event, **data}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def cpu_seconds():
    t = os.times()
    return t.user + t.system


def try_signal_existing(lock, log):
    try:
        info = json.loads(lock.read_text(encoding="utf-8"))
        t = time.perf_counter()
        with socket.create_connection(("127.0.0.1", info["port"]), timeout=1.0) as s:
            s.sendall(f"raise {info['token']}\n".encode())
            reply = s.recv(64).decode().strip()
        log("second_instance_signal", reply=reply, ms=round((time.perf_counter() - t) * 1000, 2), owner=info.get("pid"))
        return reply == "ok"
    except (OSError, ValueError, KeyError) as exc:
        log("stale_lock", error=repr(exc))
        return False


def parent_alive(handle):
    return K32.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT


class Frame(wx.Frame):
    def __init__(self, args, log):
        super().__init__(None, title="PcbAi AJ-S1 deneme", size=(480, 260))
        self.log = log
        panel = wx.Panel(self)
        self.text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.status = wx.StaticText(panel, label="Seçim: (yoklama kapalı)")
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.status, 0, wx.ALL, 6)
        sizer.Add(self.text, 1, wx.EXPAND | wx.ALL, 6)
        panel.SetSizer(sizer)
        self.Bind(wx.EVT_ACTIVATE, lambda e: (log("activate", active=e.GetActive()), e.Skip()))
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.parent = None
        if args.parent_pid:
            self.parent = K32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, args.parent_pid)
            log("parent_open", parent_pid=args.parent_pid, ok=bool(self.parent))
            self.parent_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.check_parent, self.parent_timer)
            self.parent_timer.Start(250)
        self.board = None
        if args.poll_ms:
            self.poll_n = 0
            self.poll_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.poll, self.poll_timer)
            self.poll_timer.Start(args.poll_ms)
        if args.auto_close_s:
            wx.CallLater(int(args.auto_close_s * 1000), self.Close)

    def bring_front(self, reason):
        t = time.perf_counter()
        if self.IsIconized():
            self.Iconize(False)
        self.Show()
        self.Raise()
        self.RequestUserAttention()
        U32.SetForegroundWindow(self.GetHandle())
        wx.CallLater(200, self.report_foreground, reason, t)

    def report_foreground(self, reason, t):
        fg = U32.GetForegroundWindow()
        self.log("foreground_check", reason=reason, is_foreground=fg == self.GetHandle(),
                 has_focus=wx.Window.FindFocus() is not None, ms=round((time.perf_counter() - t) * 1000, 1))

    def check_parent(self, _):
        if self.parent and not parent_alive(self.parent):
            self.log("parent_gone")
            self.Close()

    def poll(self, _):
        self.poll_n += 1
        t, c = time.perf_counter(), cpu_seconds()
        try:
            if self.board is None:
                from kipy import KiCad
                self.board = KiCad().get_board()
            items = list(self.board.get_selection())
            label = f"Seçim: {len(items)} öğe"
            err = None
        except Exception as exc:  # ölçüm: hata da kayda girer
            self.board, items, label, err = None, [], "Seçim okunamadı", repr(exc)[:200]
        self.status.SetLabel(label)
        self.log("poll", n=self.poll_n, ms=round((time.perf_counter() - t) * 1000, 2),
                 cpu_ms=round((cpu_seconds() - c) * 1000, 2), count=len(items), error=err)

    def on_close(self, event):
        self.log("close", cpu_total_s=round(cpu_seconds(), 3))
        event.Skip()


def serve(listener, token, frame, log):
    while True:
        try:
            conn, _ = listener.accept()
        except OSError:
            return
        with conn:
            line = conn.recv(256).decode(errors="replace").strip()
            ok = line == f"raise {token}"
            conn.sendall(b"ok\n" if ok else b"denied\n")
            log("raise_request", accepted=ok)
            if ok:
                wx.CallAfter(frame.bring_front, "second_click")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--log", required=True)
    p.add_argument("--state-dir", default=str(Path(__file__).resolve().parents[3] / ".pcbai-state" / "ajs1"))
    p.add_argument("--parent-pid", type=int)
    p.add_argument("--poll-ms", type=int, default=0)
    p.add_argument("--auto-close-s", type=float, default=0)
    args = p.parse_args()
    log = Log(args.log)
    log("start", python=sys.executable, wx=wx.version(), argv=sys.argv[1:])
    lock = Path(args.state_dir) / "ajs1.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    if lock.exists() and try_signal_existing(lock, log):
        log("exit_second_instance")
        return 0
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)
    token = secrets.token_hex(16)
    lock.write_text(json.dumps({"pid": os.getpid(), "port": listener.getsockname()[1], "token": token}), encoding="utf-8")
    app = wx.App(False)
    t = time.perf_counter()
    frame = Frame(args, log)
    frame.Show()
    log("shown", ms_to_show=round((time.perf_counter() - t) * 1000, 1))
    wx.CallAfter(frame.bring_front, "first_open")
    threading.Thread(target=serve, args=(listener, token, frame, log), daemon=True).start()
    try:
        app.MainLoop()
    finally:
        listener.close()
        try:
            if json.loads(lock.read_text(encoding="utf-8")).get("pid") == os.getpid():
                lock.unlink()
        except (OSError, ValueError):
            pass
        log("exit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
