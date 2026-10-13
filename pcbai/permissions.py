"""Preserve existing file permissions and protect owned application state."""
import ctypes
import os
import stat

from pcbai.core.contract import PcbAiError


def assert_unlinked(path):
    """Reject linked private write targets and Windows reparse-point ancestors."""
    for entry in (path, *path.parents):
        if entry.is_symlink() or (entry.exists() and getattr(entry.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError(f"Linked/reparse-point write target refused: {entry}")
        if entry.exists():
            info = entry.lstat()
            if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
                raise ValueError(f"Hardlink write target refused: {entry}")


def win_api():
    return ctypes.WinDLL("advapi32", use_last_error=True)


def free_local(pointer):
    free = ctypes.WinDLL("kernel32").LocalFree
    free.argtypes = [ctypes.c_void_p]
    free.restype = ctypes.c_void_p
    free(pointer)


def descriptor_for(path, information):
    api = win_api()
    getter = api.GetFileSecurityW
    getter.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p,
                       ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
    getter.restype = ctypes.c_int
    size = ctypes.c_uint32()
    getter(str(path), information, None, 0, ctypes.byref(size))
    if not size.value:
        raise PcbAiError("unsafe_permissions", "Cannot read existing security descriptor")
    buffer = ctypes.create_string_buffer(size.value)
    if not getter(str(path), information, buffer, len(buffer), ctypes.byref(size)):
        raise PcbAiError("unsafe_permissions", "Cannot read existing security descriptor")
    return buffer


def set_descriptor(path, information, descriptor):
    setter = win_api().SetFileSecurityW
    setter.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p]
    setter.restype = ctypes.c_int
    if not setter(str(path), information, descriptor):
        raise PcbAiError("unsafe_permissions", "Cannot apply file permissions; original file retained")


def windows_owner(path):
    api = win_api()
    descriptor = descriptor_for(path, 1)
    owner = ctypes.c_void_p()
    defaulted = ctypes.c_int()
    getter = api.GetSecurityDescriptorOwner
    getter.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_int)]
    getter.restype = ctypes.c_int
    if not getter(descriptor, ctypes.byref(owner), ctypes.byref(defaulted)):
        raise PcbAiError("unsafe_state", "Cannot read state directory owner")
    text = ctypes.c_void_p()
    convert = api.ConvertSidToStringSidW
    convert.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    convert.restype = ctypes.c_int
    if not convert(owner, ctypes.byref(text)):
        raise PcbAiError("unsafe_state", "Cannot resolve state directory owner")
    try:
        return ctypes.wstring_at(text)
    finally:
        free_local(text)


def private_windows_acl(paths, sid):
    descriptor = ctypes.c_void_p()
    convert = win_api().ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    convert.restype = ctypes.c_int
    if not convert(f"D:P(A;OICI;FA;;;{sid})", 1, ctypes.byref(descriptor), None):
        raise PcbAiError("unsafe_state", "Cannot construct private state ACL")
    try:
        for path in paths:
            set_descriptor(path, 0x80000004, descriptor)
    finally:
        free_local(descriptor)


def preserve_permissions(source, destination):
    if os.name == "nt":
        descriptor = descriptor_for(source, 5)  # OWNER + DACL
        control, revision = ctypes.c_uint16(), ctypes.c_uint32()
        getter = win_api().GetSecurityDescriptorControl
        getter.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(ctypes.c_uint32)]
        getter.restype = ctypes.c_int
        if not getter(descriptor, ctypes.byref(control), ctypes.byref(revision)):
            raise PcbAiError("unsafe_permissions", "Cannot read file ACL control flags")
        protected = 0x80000000 if control.value & 0x1000 else 0x20000000
        set_descriptor(destination, 5 | protected, descriptor)
    else:
        metadata = os.stat(source, follow_symlinks=False)
        os.chown(destination, metadata.st_uid, metadata.st_gid)
        os.chmod(destination, stat.S_IMODE(metadata.st_mode))
