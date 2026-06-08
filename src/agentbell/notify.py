"""Windows notification and sound playback.

Uses a detached subprocess with ctypes to create a top-most notification window.
No PowerShell dependency. Works on Windows 11.
"""

import os
import subprocess
import sys
import tempfile
import threading
import time

from agentbell.logging_utils import setup_logging

logger = setup_logging()

_SOUND_MAP = {
    "permission": "SystemExclamation",
    "done": "SystemNotification",
    "test": "SystemAsterisk",
}

# The notification window script, run as a detached subprocess
_NOTIFY_SCRIPT = r'''
import ctypes, ctypes.wintypes, struct, sys, winsound

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

LRESULT = ctypes.c_longlong if sys.maxsize > 2**32 else ctypes.c_long
LP = ctypes.c_longlong if sys.maxsize > 2**32 else ctypes.c_long
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, LP)
user32.DefWindowProcW.argtypes = [ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, LP]
user32.DefWindowProcW.restype = LRESULT

class PS(ctypes.Structure):
    _fields_=[('hdc',ctypes.wintypes.HDC),('fErase',ctypes.wintypes.BOOL),
              ('rc',ctypes.wintypes.RECT),('fR',ctypes.wintypes.BOOL),
              ('fI',ctypes.wintypes.BOOL),('r',ctypes.c_byte*32)]

title = sys.argv[1]
msg = sys.argv[2]
duration = int(sys.argv[3])
sound = sys.argv[4] if len(sys.argv) > 4 else 'SystemNotification'

# Play sound in a background thread so window appears immediately
import threading
def _play():
    try:
        winsound.PlaySound(sound, winsound.SND_ALIAS)
    except Exception:
        pass
threading.Thread(target=_play, daemon=True).start()

def wp(h, ms, wp, lp):
    if ms == 0x000F:  # WM_PAINT
        ps = PS()
        hdc = user32.BeginPaint(h, ctypes.byref(ps))
        bg = gdi32.CreateSolidBrush(0x002E1E2E)
        user32.FillRect(hdc, ctypes.byref(ps.rc), bg)
        gdi32.DeleteObject(bg)
        rc = ctypes.wintypes.RECT()
        user32.GetClientRect(h, ctypes.byref(rc))
        gdi32.SetBkMode(hdc, 1)
        gdi32.SetTextColor(hdc, 0x00E7C6FF)
        f = gdi32.CreateFontW(-16, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        o = gdi32.SelectObject(hdc, f)
        r = ctypes.wintypes.RECT(rc.left + 36, rc.top + 12, rc.right - 10, rc.top + 36)
        user32.DrawTextW(hdc, title, -1, ctypes.byref(r), 0)
        gdi32.SelectObject(hdc, o)
        gdi32.DeleteObject(f)
        gdi32.SetTextColor(hdc, 0x00D4D4E0)
        f2 = gdi32.CreateFontW(-14, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        o = gdi32.SelectObject(hdc, f2)
        r2 = ctypes.wintypes.RECT(rc.left + 36, rc.top + 38, rc.right - 10, rc.bottom - 8)
        user32.DrawTextW(hdc, msg, -1, ctypes.byref(r2), 0)
        gdi32.SelectObject(hdc, o)
        gdi32.DeleteObject(f2)
        ic = user32.LoadIconW(0, 32516)
        user32.DrawIconEx(hdc, 8, 14, ic, 24, 24, 0, 0, 3)
        user32.EndPaint(h, ctypes.byref(ps))
        return 0
    elif ms == 0x0020:  # WM_SETCURSOR
        IDC_ARROW = 32512
        user32.SetCursor(user32.LoadCursorW(0, IDC_ARROW))
        return 1
    elif ms == 0x0113:  # WM_TIMER
        user32.DestroyWindow(h)
        return 0
    elif ms == 0x0002:  # WM_DESTROY
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(h, ms, wp, lp)

proc = WNDPROC(wp)

class WC(ctypes.Structure):
    _fields_=[('s',ctypes.c_uint),('p',WNDPROC),('c1',ctypes.c_int),('c2',ctypes.c_int),
              ('hi',ctypes.wintypes.HINSTANCE),('ic',ctypes.wintypes.HICON),
              ('cr',ctypes.wintypes.HANDLE),('bg',ctypes.wintypes.HANDLE),
              ('mn',ctypes.wintypes.LPCWSTR),('cn',ctypes.wintypes.LPCWSTR)]

IDC_ARROW = 32512
w = WC()
w.p = proc
w.cn = 'AgentBellToast'
w.cr = user32.LoadCursorW(0, IDC_ARROW)
user32.RegisterClassW(ctypes.byref(w))

sw = user32.GetSystemMetrics(0)
sh = user32.GetSystemMetrics(1)
W, H = 340, 85

ex = 0x00000008 | 0x00000080 | 0x08000000  # WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
h = user32.CreateWindowExW(ex, 'AgentBellToast', 'AB', 0x80000000,  # WS_POPUP
    sw - W - 20, sh - H - 60, W, H, 0, 0, 0, None)
user32.ShowWindow(h, 5)  # SW_SHOWNOACTIVATE
user32.SetWindowPos(h, -1, sw - W - 20, sh - H - 60, W, H, 0x0010 | 0x0040)
user32.UpdateWindow(h)
user32.SetTimer(h, 1, duration * 1000, None)

msg = ctypes.wintypes.MSG()
while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0):
    user32.TranslateMessage(ctypes.byref(msg))
    user32.DispatchMessageW(ctypes.byref(msg))
'''


def send_notification(
    title: str,
    message: str,
    kind: str = "notification",
    source: str = "agentbell",
    duration: int = 6,
) -> None:
    """Send a notification popup without stealing focus.

    Launches a detached subprocess with a ctypes top-most window.
    Sound is played inside the subprocess so it completes before exit.
    """
    logger.info("Sending notification: title=%r, kind=%r, source=%r", title, kind, source)

    sound = _SOUND_MAP.get(kind, "SystemNotification")

    try:
        # Write the notification script to a temp file
        script_path = os.path.join(tempfile.gettempdir(), "agentbell_toast.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(_NOTIFY_SCRIPT)

        # Use pythonw.exe (no console window) for GUI subprocess
        python_dir = os.path.dirname(sys.executable)
        pythonw = os.path.join(python_dir, "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable  # fallback

        subprocess.Popen(
            [pythonw, script_path, title, message, str(duration), sound],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        logger.info("Notification subprocess launched.")

        # Clean up temp file after a delay
        def cleanup():
            time.sleep(duration + 2)
            try:
                os.unlink(script_path)
            except OSError:
                pass

        threading.Thread(target=cleanup, daemon=True).start()
    except Exception as e:
        logger.error("Failed to send notification: %s", e)
        raise
