"""Bounded external processes with process-tree termination and bounded output tails."""
import os
import signal
import subprocess
import tempfile
import time

from pcbai.core.contract import PcbAiError


def run_process(argv, *, cwd, timeout, env=None):
    if not 0 < timeout <= 3630:
        raise PcbAiError("invalid_arguments", "External engine timeout must be 0–3630 seconds")
    start = time.monotonic()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        def tail(stream):
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - 4096))
            return stream.read().decode("utf-8", errors="replace")

        try:
            process = subprocess.Popen([str(a) for a in argv], cwd=cwd, env=env, shell=False,
                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                start_new_session=os.name != "nt",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except OSError as exc:
            raise PcbAiError("external_error", str(exc)) from exc
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            if os.name == "nt":
                # /T terminates the tree, /PID limits the action to our own launched process.
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], shell=False,
                    timeout=10, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.kill()
            process.wait(timeout=10)
            raise PcbAiError("timeout", f"External engine exceeded {timeout}s; process tree terminated",
                             details=dict(argv=[str(a) for a in argv], stdout_tail=tail(stdout),
                                          stderr_tail=tail(stderr))) from exc

        return dict(returncode=process.returncode, seconds=round(time.monotonic() - start, 6),
                    stdout_tail=tail(stdout), stderr_tail=tail(stderr), argv=[str(a) for a in argv])
