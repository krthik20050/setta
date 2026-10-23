"""Windows work-area bounds exclude the taskbar and other docked toolbars."""
import ctypes
from ctypes import wintypes


class QuietWalk:
    """Short purposeful strolls with idle pauses; no vertical bouncing."""
    def __init__(self, x, bounds, width, height, now):
        self.bounds, self.width, self.height = bounds, width, height
        self.x = float(x)
        self.direction = -1
        self.phase = 'idle'
        self.until = now + 3
        self.previous = now
        self.travelled = 0.0

    def step(self, now):
        dt = min(.1, max(0, now - self.previous))
        self.previous = now
        left, top, right, bottom = self.bounds
        low, high = left + 12, max(left + 12, right - self.width - 12)
        self.x = max(low, min(high, self.x))
        if now >= self.until:
            if self.phase == 'idle':
                self.phase, self.until = 'walk', now + 9
                if self.x <= low + 2:
                    self.direction = 1
                elif self.x >= high - 2:
                    self.direction = -1
            else:
                self.phase, self.until = 'idle', now + 5
                self.direction *= -1
        if self.phase == 'walk':
            advance = self.direction * 24 * dt
            proposed = self.x + advance
            clipped = max(low, min(high, proposed))
            self.travelled += abs(clipped - self.x)
            self.x = clipped
            if proposed <= low or proposed >= high:
                self.phase, self.until = 'idle', now + 4
                self.direction *= -1
        return round(self.x), max(top, bottom - self.height), self.phase, self.direction


def work_area(x, y):
    class MonitorInfo(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT),
                    ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD)]

    user32 = ctypes.windll.user32
    user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    user32.MonitorFromPoint.restype = wintypes.HANDLE
    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    monitor = user32.MonitorFromPoint(wintypes.POINT(x, y), 2)
    info = MonitorInfo()
    info.cbSize = ctypes.sizeof(info)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        raise ctypes.WinError()
    r = info.rcWork
    return r.left, r.top, r.right, r.bottom


def next_position(x, direction, bounds, width=192, height=208, distance=2):
    left, top, right, bottom = bounds
    low, high = left + 8, max(left + 8, right - width - 8)
    x = max(low, min(high, x))
    if x + direction * distance <= low:
        direction = 1
    elif x + direction * distance >= high:
        direction = -1
    return max(low, min(high, x + direction * distance)), max(top, bottom - height), direction


def roam_position(x, y, dx, dy, bounds, width=192, height=208, distance=2):
    left, top, right, bottom = bounds
    low_x, high_x = left + 8, max(left + 8, right - width - 8)
    low_y, high_y = top + 8, max(top + 8, bottom - height)
    x, y = max(low_x, min(high_x, x)), max(low_y, min(high_y, y))
    if not low_x < x + dx * distance < high_x:
        dx = 1 if x + dx * distance <= low_x else -1
    vertical = distance * 0.65
    if not low_y < y + dy * vertical < high_y:
        dy = 1 if y + dy * vertical <= low_y else -1
    return (round(max(low_x, min(high_x, x + dx * distance))),
            round(max(low_y, min(high_y, y + dy * vertical))), dx, dy)
