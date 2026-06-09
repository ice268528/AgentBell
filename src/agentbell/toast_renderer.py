"""Claude-styled toast notification using ctypes + GDI.

Renders a Claude/Anthropic warm-dark themed notification window
using direct Windows API calls. No PowerShell or HTA dependency.
"""

import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from agentbell.logging_utils import setup_logging
from agentbell.theme import (
    ACCENT_HOVER,
    ACCENT_PRIMARY,
    ACCENT_PRESSED,
    ANIMATION_DURATION_MS,
    AUTO_COLLAPSE_MS,
    EVENT_COLORS,
    FONT_FAMILY,
    FONT_MONO,
    LIGHT,
    MID_GRAY,
    ORANGE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TOAST_BG,
    TOAST_BG_ELEVATED,
    AgentBellConfig,
    ClaudeHookToastEvent,
)

logger = setup_logging()

# ── Color helpers (BGR for GDI) ──────────────────────────────────────────────
def _hex_to_bgr(hex_color: str) -> int:
    """Convert '#RRGGBB' to 0x00BBGGRR for GDI."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


_BG_COLOR = _hex_to_bgr(TOAST_BG)
_ACCENT_COLOR = _hex_to_bgr(ACCENT_PRIMARY)
_TITLE_COLOR = _hex_to_bgr(TEXT_PRIMARY)
_DESC_COLOR = _hex_to_bgr(TEXT_SECONDARY)
_EYEBROW_COLOR = _hex_to_bgr(MID_GRAY)
_ICON_BG = _hex_to_bgr(ACCENT_PRESSED)
_ICON_FG = _hex_to_bgr(LIGHT)

# ── Window dimensions ────────────────────────────────────────────────────────
TOAST_W = 380
TOAST_H = 130
PADDING = 16
ICON_SIZE = 36
BORDER_RADIUS = 16


def _generate_toast_script(event: ClaudeHookToastEvent, config: AgentBellConfig | None = None) -> str:
    """Generate a Python script that creates a Claude-styled toast window."""
    cfg = config or AgentBellConfig()
    accent_bgr = _hex_to_bgr(event.accent_color)

    title = event.title or {
        "permission_required": "Claude Code 需要授权",
        "task_done": "Claude Code 任务完成",
        "error": "Claude Code 执行失败",
        "info": "Claude Code 通知",
    }.get(event.type, "Claude Code 通知")

    desc = event.message or {
        "permission_required": "需要你确认工具调用以继续执行。",
        "task_done": "当前任务已完成。",
        "error": "执行过程中出现错误。",
        "info": "",
    }.get(event.type, "")

    eyebrow = {
        "permission_required": "等待授权",
        "task_done": "已完成",
        "error": "错误",
        "info": "通知",
    }.get(event.type, "通知")

    # Escape for Python string
    title_esc = title.replace("\\", "\\\\").replace('"', '\\"')
    desc_esc = desc.replace("\\", "\\\\").replace('"', '\\"')
    eyebrow_esc = eyebrow.replace("\\", "\\\\").replace('"', '\\"')

    return f'''import ctypes, ctypes.wintypes, sys, time, winsound, threading

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

class RECT(ctypes.Structure):
    _fields_=[('left',ctypes.c_long),('top',ctypes.c_long),('right',ctypes.c_long),('bottom',ctypes.c_long)]

title = "{title_esc}"
desc = "{desc_esc}"
eyebrow = "{eyebrow_esc}"
accent = {accent_bgr}
bg = {_BG_COLOR}
title_color = {_TITLE_COLOR}
desc_color = {_DESC_COLOR}
eyebrow_color = {_EYEBROW_COLOR}
icon_bg = {_ICON_BG}
icon_fg = {_ICON_FG}
duration = {cfg.auto_collapse_ms // 1000 + 6}

def rounded_rect(hdc, x, y, w, h, r):
    gdi32.RoundRect(hdc, x, y, x+w, y+h, r, r)

def wp(h, ms, wp, lp):
    if ms == 0x000F:
        ps = PS()
        hdc = user32.BeginPaint(h, ctypes.byref(ps))
        rc = RECT()
        user32.GetClientRect(h, ctypes.byref(rc))
        w = rc.right - rc.left
        ht = rc.bottom - rc.top

        # Background
        bg_brush = gdi32.CreateSolidBrush(bg)
        user32.FillRect(hdc, ctypes.byref(rc), bg_brush)
        gdi32.DeleteObject(bg_brush)

        # Accent bar at top
        accent_brush = gdi32.CreateSolidBrush(accent)
        bar_rect = RECT(0, 0, w, 3)
        user32.FillRect(hdc, ctypes.byref(bar_rect), accent_brush)
        gdi32.DeleteObject(accent_brush)

        # Icon background (rounded square)
        icon_brush = gdi32.CreateSolidBrush(icon_bg)
        old_brush = gdi32.SelectObject(hdc, icon_brush)
        old_pen = gdi32.SelectObject(hdc, gdi32.GetStockObject(0))  # NULL_PEN
        rounded_rect(hdc, 20, 22, {ICON_SIZE}, {ICON_SIZE}, 10)
        gdi32.SelectObject(hdc, old_brush)
        gdi32.SelectObject(hdc, old_pen)
        gdi32.DeleteObject(icon_brush)

        # Icon text ">_"
        gdi32.SetBkMode(hdc, 1)  # TRANSPARENT
        gdi32.SetTextColor(hdc, icon_fg)
        icon_font = gdi32.CreateFontW(-14, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_font = gdi32.SelectObject(hdc, icon_font)
        icon_rect = RECT(20, 22, 20+{ICON_SIZE}, 22+{ICON_SIZE})
        user32.DrawTextW(hdc, '>_', -1, ctypes.byref(icon_rect), 0x0001 | 0x0004)  # DT_CENTER | DT_VCENTER
        gdi32.SelectObject(hdc, old_font)
        gdi32.DeleteObject(icon_font)

        # Eyebrow
        gdi32.SetTextColor(hdc, eyebrow_color)
        meta_font = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_font = gdi32.SelectObject(hdc, meta_font)
        # Dot
        dot_brush = gdi32.CreateSolidBrush(accent)
        old_b = gdi32.SelectObject(hdc, dot_brush)
        gdi32.Ellipse(hdc, 66, 26, 73, 33)
        gdi32.SelectObject(hdc, old_b)
        gdi32.DeleteObject(dot_brush)
        # Text
        eb_rect = RECT(80, 22, w-20, 36)
        user32.DrawTextW(hdc, eyebrow, -1, ctypes.byref(eb_rect), 0)
        gdi32.SelectObject(hdc, old_font)
        gdi32.DeleteObject(meta_font)

        # Title
        gdi32.SetTextColor(hdc, title_color)
        title_font = gdi32.CreateFontW(-15, 0, 0, 0, 650, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_font = gdi32.SelectObject(hdc, title_font)
        t_rect = RECT(66, 38, w-20, 58)
        user32.DrawTextW(hdc, title, -1, ctypes.byref(t_rect), 0)
        gdi32.SelectObject(hdc, old_font)
        gdi32.DeleteObject(title_font)

        # Description
        if desc:
            gdi32.SetTextColor(hdc, desc_color)
            desc_font = gdi32.CreateFontW(-13, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
            old_font = gdi32.SelectObject(hdc, desc_font)
            d_rect = RECT(66, 58, w-20, 80)
            user32.DrawTextW(hdc, desc, -1, ctypes.byref(d_rect), 0)
            gdi32.SelectObject(hdc, old_font)
            gdi32.DeleteObject(desc_font)

        # Button area - "打开 Claude Code"
        btn_x = w - 130
        btn_y = ht - 38
        btn_w = 110
        btn_h = 28
        btn_brush = gdi32.CreateSolidBrush(accent)
        old_b = gdi32.SelectObject(hdc, btn_brush)
        old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(0))
        rounded_rect(hdc, btn_x, btn_y, btn_w, btn_h, 8)
        gdi32.SelectObject(hdc, old_b)
        gdi32.SelectObject(hdc, old_p)
        gdi32.DeleteObject(btn_brush)
        gdi32.SetTextColor(hdc, icon_fg)
        btn_font = gdi32.CreateFontW(-12, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_font = gdi32.SelectObject(hdc, btn_font)
        btn_rect = RECT(btn_x, btn_y, btn_x+btn_w, btn_y+btn_h)
        user32.DrawTextW(hdc, '打开 Claude Code', -1, ctypes.byref(btn_rect), 0x0001 | 0x0004)
        gdi32.SelectObject(hdc, old_font)
        gdi32.DeleteObject(btn_font)

        user32.EndPaint(h, ctypes.byref(ps))
        return 0
    elif ms == 0x0020:  # WM_SETCURSOR
        user32.SetCursor(user32.LoadCursorW(0, 32512))
        return 1
    elif ms == 0x0113:  # WM_TIMER
        user32.DestroyWindow(h)
        return 0
    elif ms == 0x0002:  # WM_DESTROY
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(h, ms, wp, lp)

# Sound
def _play():
    try:
        winsound.PlaySound('SystemNotification', winsound.SND_ALIAS)
    except: pass
threading.Thread(target=_play, daemon=True).start()

proc = WNDPROC(wp)
class WC(ctypes.Structure):
    _fields_=[('s',ctypes.c_uint),('p',WNDPROC),('c1',ctypes.c_int),('c2',ctypes.c_int),
              ('hi',ctypes.wintypes.HINSTANCE),('ic',ctypes.wintypes.HICON),
              ('cr',ctypes.wintypes.HANDLE),('bg',ctypes.wintypes.HANDLE),
              ('mn',ctypes.wintypes.LPCWSTR),('cn',ctypes.wintypes.LPCWSTR)]

w = WC()
w.p = proc
w.cn = 'ClaudeToast'
w.cr = user32.LoadCursorW(0, 32512)
user32.RegisterClassW(ctypes.byref(w))

sw = user32.GetSystemMetrics(0)
sh = user32.GetSystemMetrics(1)
W, H = {TOAST_W}, {TOAST_H}

ex = 0x00000008 | 0x00000080 | 0x08000000  # WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
h = user32.CreateWindowExW(ex, 'ClaudeToast', 'AgentBell', 0x80000000,
    sw - W - 24, sh - H - 60, W, H, 0, 0, 0, None)
user32.ShowWindow(h, 5)  # SW_SHOWNOACTIVATE
user32.SetWindowPos(h, -1, sw - W - 24, sh - H - 60, W, H, 0x0010 | 0x0040)
user32.UpdateWindow(h)
user32.SetTimer(h, 1, duration * 1000, None)

msg = ctypes.wintypes.MSG()
while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0):
    user32.TranslateMessage(ctypes.byref(msg))
    user32.DispatchMessageW(ctypes.byref(msg))
'''


def show_toast(
    event: ClaudeHookToastEvent,
    config: AgentBellConfig | None = None,
    duration: int = 12,
) -> None:
    """Show a Claude-styled toast notification."""
    cfg = config or AgentBellConfig()
    logger.info("Showing toast: type=%r, title=%r", event.type, event.title)

    script = _generate_toast_script(event, cfg)

    # Write to temp file
    script_path = os.path.join(tempfile.gettempdir(), f"agentbell_toast_{uuid.uuid4().hex[:8]}.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    # Use pythonw.exe for GUI subprocess
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    try:
        subprocess.Popen(
            [pythonw, script_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Toast subprocess launched.")
    except Exception as e:
        logger.error("Failed to launch toast: %s", e)

    # Cleanup
    def cleanup():
        time.sleep(duration + 2)
        try:
            os.unlink(script_path)
        except OSError:
            pass

    threading.Thread(target=cleanup, daemon=True).start()


def show_permission_toast(
    title: str | None = None,
    message: str | None = None,
    tool_name: str | None = None,
    command: str | None = None,
    project_path: str | None = None,
    config: AgentBellConfig | None = None,
) -> None:
    """Show a permission request toast."""
    event = ClaudeHookToastEvent(
        id=uuid.uuid4().hex[:12],
        type="permission_required",
        title=title,
        message=message,
        tool_name=tool_name,
        command=command,
        project_path=project_path,
    )
    show_toast(event, config)


def show_done_toast(
    title: str | None = None,
    message: str | None = None,
    config: AgentBellConfig | None = None,
) -> None:
    """Show a task done toast."""
    event = ClaudeHookToastEvent(
        id=uuid.uuid4().hex[:12],
        type="task_done",
        title=title,
        message=message,
    )
    show_toast(event, config)
