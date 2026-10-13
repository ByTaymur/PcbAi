"""WSL argv and drive conversion. No command strings or Linux shells."""
import os
import re
import shutil
from pathlib import PureWindowsPath

from pcbai.core.contract import PcbAiError


def parse_spec(value):
    match = re.fullmatch(r"wsl:([A-Za-z0-9._-]+):(/[A-Za-z0-9._/-]+)", value)
    if not match or ".." in match.group(2).split("/"):
        raise PcbAiError("invalid_config", "Use wsl:<distribution>:<absolute Linux executable>")
    return match.groups()


def linux_path(value):
    path = PureWindowsPath(value)
    if not re.fullmatch(r"[A-Za-z]:", path.drive) or not path.root or ".." in path.parts:
        raise PcbAiError("invalid_arguments", "WSL requires an absolute local drive path; UNC paths are refused")
    if os.name == "nt":
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(path.drive + "\\") != 3:
            raise PcbAiError("invalid_arguments", "WSL engine files must be on a fixed local drive")
    return "/mnt/" + path.drive[0].lower() + "/" + "/".join(path.parts[1:])


def argv(spec, arguments, timeout, *, home=None):
    distro, executable = parse_spec(spec)
    launcher = shutil.which("wsl.exe")
    if not launcher:
        raise PcbAiError("missing_dependency", "WSL not found; run pcbai doctor")
    # GNU timeout owns the Linux process group, even if the Windows client is terminated.
    isolated = (["env", "HOME=" + linux_path(home), "XDG_CONFIG_HOME=" + linux_path(home) + "/config",
                 "XDG_CACHE_HOME=" + linux_path(home) + "/cache"] if home is not None else [])
    return [launcher, "-d", distro, "--exec", *isolated, "timeout", "--signal=TERM", "--kill-after=5",
            str(timeout), executable, *arguments]
