"""Small, read-only context snapshots; never reads files or captures the screen."""
import ctypes
from ctypes import wintypes
from datetime import datetime
import os
from pathlib import PureWindowsPath
import time

from .companion_context import Observation


def foreground_window(*, skip_own: bool = False, include_title: bool = False) -> dict | None:
    if os.name != 'nt':
        return None
    user = ctypes.WinDLL('user32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    hwnd = user.GetForegroundWindow()
    if not hwnd:
        return None
    process_id = wintypes.DWORD()
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    if skip_own and process_id.value == os.getpid():
        return None
    handle = kernel.OpenProcess(0x1000, False, process_id.value)
    if not handle:
        return None
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        if kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
            title = ''
            if include_title:
                user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
                title_buffer = ctypes.create_unicode_buffer(513)
                user.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
                title = title_buffer.value
            return {'app': PureWindowsPath(buffer.value).name, 'title': title,
                    'pid': process_id.value}
    finally:
        kernel.CloseHandle(handle)
    return None


def foreground_app() -> str | None:
    window = foreground_window()
    return window['app'] if window else None


def desktop_observations(settings: dict) -> list[Observation]:
    observed = time.monotonic()
    result = []
    if settings.get('date_time', True):
        result.append(Observation('local_date_time', datetime.now().astimezone().isoformat(),
                                  'operating_system_clock', 1.0, observed, 10))
    if settings.get('foreground_app', False):
        app = foreground_app()
        if app:
            result.append(Observation('foreground_app', app, 'windows_foreground_process',
                                      1.0, observed, 5))
    return result
