import ctypes
from ctypes import wintypes


class MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def set_windows_titlebar_theme(window, dark):
    user = ctypes.WinDLL("user32")
    user.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
    user.GetAncestor.restype = wintypes.HWND
    hwnd = user.GetAncestor(window.winfo_id(), 2)
    if not hwnd:
        return

    dwm = ctypes.WinDLL("dwmapi")
    dwm.DwmSetWindowAttribute.argtypes = (
        wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
    )
    value = wintypes.BOOL(dark)
    if dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)) != 0:
        dwm.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(value), ctypes.sizeof(value))

    user.RedrawWindow.argtypes = (wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT)
    user.RedrawWindow(hwnd, None, None, 0x0400 | 0x0100 | 0x0001)  # FRAME | UPDATENOW | INVALIDATE


def center_windows_dialog(dialog):
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
    user.GetAncestor.restype = wintypes.HWND
    user.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
    user.MonitorFromWindow.restype = wintypes.HANDLE
    user.GetMonitorInfoW.argtypes = (wintypes.HANDLE, ctypes.POINTER(MonitorInfo))
    user.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, wintypes.UINT)

    window = user.GetAncestor(dialog.winfo_id(), 2)
    owner = user.GetAncestor(dialog.master.winfo_id(), 2)
    monitor = user.MonitorFromWindow(owner, 2)
    info = MonitorInfo()
    info.cbSize = ctypes.sizeof(info)
    outer = wintypes.RECT()
    if not (user.GetMonitorInfoW(monitor, ctypes.byref(info))
            and user.GetWindowRect(window, ctypes.byref(outer))):
        return

    visible = wintypes.RECT()
    dwm = ctypes.WinDLL("dwmapi")
    dwm.DwmGetWindowAttribute.argtypes = (
        wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
    )
    if dwm.DwmGetWindowAttribute(window, 9, ctypes.byref(visible), ctypes.sizeof(visible)) != 0:
        visible = outer

    screen = info.rcMonitor
    x = outer.left + (screen.left + screen.right - visible.left - visible.right) // 2
    y = outer.top + (screen.top + screen.bottom - visible.top - visible.bottom) // 2
    # Keep the window size, stacking order, and keyboard focus unchanged.
    user.SetWindowPos(window, None, x, y, 0, 0, 0x0001 | 0x0004 | 0x0010)
