"""A per-user Windows mutex prevents two camera-owning companion processes."""
import ctypes
from ctypes import wintypes
import hashlib
import os

from .paths import PROJECT_ROOT, RUNTIME_DIR


def acquire_instance():
    if os.name != 'nt':
        return None, True
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    digest = hashlib.sha256(str(PROJECT_ROOT).casefold().encode()).hexdigest()[:20]
    handle = kernel.CreateMutexW(None, False, 'Local\\SettaHub-' + digest)
    error = ctypes.get_last_error()
    if not handle:
        raise ctypes.WinError(error)
    if error == 183:
        release_instance(handle)
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        (RUNTIME_DIR / '.open-hub').write_text('open', encoding='utf-8')
        return None, False
    return handle, True


def release_instance(handle):
    if handle and os.name == 'nt':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        kernel.CloseHandle(handle)
