"""Claude-styled toast notification with full interactivity.

Supports three states:
- Compact: default view with title, description, buttons
- Expanded: shows detail panel with tool/command/project info
- Mini Pill: auto-collapses after 10s, click to re-expand

Uses ctypes + GDI for rendering. No PowerShell dependency.
All colors from Claude/Anthropic theme tokens.
No hardcoded fake data - fields come from real hook events.
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
    AUTO_COLLAPSE_MS,
    EVENT_COLORS,
    LIGHT,
    MID_GRAY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TOAST_BG,
    TOAST_BG_ELEVATED,
    AgentBellConfig,
    ClaudeHookToastEvent,
)

logger = setup_logging()

# ── GDI constants ────────────────────────────────────────────────────────────
NULL_PEN = 8
TRANSPARENT = 1
DT_CENTER = 1
DT_RIGHT = 2
DT_VCENTER = 4


def _hex_to_bgr(hex_color: str) -> int:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


# ── Theme BGR ────────────────────────────────────────────────────────────────
_BG = _hex_to_bgr(TOAST_BG)
_BG_ELEVATED = _hex_to_bgr(TOAST_BG_ELEVATED)
_ACCENT = _hex_to_bgr(ACCENT_PRIMARY)
_ACCENT_HOVER = _hex_to_bgr(ACCENT_HOVER)
_TEXT_PRIMARY_BGR = _hex_to_bgr(TEXT_PRIMARY)
_TEXT_SECONDARY_BGR = _hex_to_bgr(TEXT_SECONDARY)
_MID_GRAY_BGR = _hex_to_bgr(MID_GRAY)
_LIGHT_BGR = _hex_to_bgr(LIGHT)

# Semi-transparent approximations (solid BGR)
_GHOST_BG = 0x001A1917
_GHOST_BORDER = 0x00201F1D
_ICON_BG = 0x001E2A29  # rgba(217,119,87,0.12)
_ICON_BORDER = 0x003C4E5E  # rgba(217,119,87,0.24)


def _generate_toast_script(event: ClaudeHookToastEvent, config: AgentBellConfig | None = None) -> str:
    cfg = config or AgentBellConfig()
    accent = _hex_to_bgr(event.accent_color)

    title = event.title or {
        "permission_required": "Claude Code 需要授权",
        "task_done": "Claude Code 任务完成",
        "error": "Claude Code 执行失败",
        "info": "Claude Code 通知",
    }.get(event.type, "Claude Code 通知")

    desc = event.message or {
        "permission_required": "需要你确认工具调用以继续执行。",
        "task_done": "当前任务已完成，等待你的下一步。",
        "error": "执行过程中出现错误。",
        "info": "",
    }.get(event.type, "")

    eyebrow = {
        "permission_required": "等待授权",
        "task_done": "已完成",
        "error": "错误",
        "info": "通知",
    }.get(event.type, "通知")

    icon_symbol = {
        "permission_required": ">_",
        "task_done": "\\u2713",
        "error": "!",
        "info": "i",
    }.get(event.type, ">_")

    primary_btn = {
        "permission_required": "打开 Claude Code",
        "task_done": "查看结果",
        "error": "查看错误",
        "info": "打开 Claude Code",
    }.get(event.type, "打开 Claude Code")

    # Detail data from real event (empty string if not provided)
    tool_name = event.tool_name or ""
    command = event.command or ""
    project_path = event.project_path or ""
    has_detail = bool(tool_name or command or project_path)

    auto_collapse_ms = cfg.auto_collapse_ms

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

# ── GDI constants ──
NULL_PEN = 8
TRANSPARENT = 1
DT_CENTER = 1
DT_RIGHT = 2
DT_VCENTER = 4

# ── Theme (BGR) ──
BG = {_BG}
BG_ELEVATED = {_BG_ELEVATED}
ACCENT = {accent}
TEXT_PRIMARY = {_TEXT_PRIMARY_BGR}
TEXT_SECONDARY = {_TEXT_SECONDARY_BGR}
MID_GRAY = {_MID_GRAY_BGR}
LIGHT = {_LIGHT_BGR}
GHOST_BG = {_GHOST_BG}
ICON_BG = {_ICON_BG}
ICON_BORDER_COLOR = {_ICON_BORDER}

# ── Data (from real hook event, no fake data) ──
title = "{_esc(title)}"
desc = "{_esc(desc)}"
eyebrow = "{_esc(eyebrow)}"
icon_symbol = "{icon_symbol}"
primary_text = "{_esc(primary_btn)}"
tool_name = "{_esc(tool_name)}"
cmd_text = "{_esc(command)}"
proj_path = "{_esc(project_path)}"
has_detail = {"True" if has_detail else "False"}
duration = {auto_collapse_ms // 1000 + 12}

# ── Fallback text when detail is missing ──
DETAIL_FALLBACK = "工具调用详情暂不可用"
DETAIL_HINT = "请回到 Claude Code 终端查看完整授权信息。"

# ── State ──
state = "compact"  # compact | expanded | pill
hwnd_ref = [0]

# ── Layout ──
COMPACT_W, COMPACT_H = 380, 140
EXPANDED_W, EXPANDED_H = 400, 240
PILL_W, PILL_H = 160, 36
PAD = 16
ICON_SZ = 36
ICON_TEXT_GAP = 12
BTN_H = 34
BTN_RADIUS = 10
PRIMARY_BTN_W = 124
GHOST_BTN_W = 72
BTN_GAP = 8

# ── Button hit rects ──
btn_primary_rect = [0, 0, 0, 0]
btn_secondary_rect = [0, 0, 0, 0]
btn_close_rect = [0, 0, 0, 0]
btn_pill_rect = [0, 0, 0, 0]

def pt_in_rect(px, py, r):
    return r[0] <= px <= r[2] and r[1] <= py <= r[3]

def fill_bg(hdc, w, h, color):
    brush = gdi32.CreateSolidBrush(color)
    rc = RECT(0, 0, w, h)
    user32.FillRect(hdc, ctypes.byref(rc), brush)
    gdi32.DeleteObject(brush)

def fill_rect_color(hdc, x, y, w, h, color):
    brush = gdi32.CreateSolidBrush(color)
    rc = RECT(x, y, x+w, y+h)
    user32.FillRect(hdc, ctypes.byref(rc), brush)
    gdi32.DeleteObject(brush)

def draw_rounded_rect_filled(hdc, x, y, w, h, r, color):
    brush = gdi32.CreateSolidBrush(color)
    old_b = gdi32.SelectObject(hdc, brush)
    old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
    gdi32.RoundRect(hdc, x, y, x+w, y+h, r, r)
    gdi32.SelectObject(hdc, old_b)
    gdi32.SelectObject(hdc, old_p)
    gdi32.DeleteObject(brush)

def draw_text_centered(hdc, x, y, w, h, text, color, font_size, weight):
    gdi32.SetBkMode(hdc, TRANSPARENT)
    gdi32.SetTextColor(hdc, color)
    f = gdi32.CreateFontW(font_size, 0, 0, 0, weight, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
    o = gdi32.SelectObject(hdc, f)
    r = RECT(x, y, x+w, y+h)
    user32.DrawTextW(hdc, text, -1, ctypes.byref(r), DT_CENTER | DT_VCENTER)
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(f)

def draw_text_left(hdc, x, y, w, h, text, color, font_size, weight):
    gdi32.SetBkMode(hdc, TRANSPARENT)
    gdi32.SetTextColor(hdc, color)
    f = gdi32.CreateFontW(font_size, 0, 0, 0, weight, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
    o = gdi32.SelectObject(hdc, f)
    r = RECT(x, y, x+w, y+h)
    user32.DrawTextW(hdc, text, -1, ctypes.byref(r), DT_VCENTER)
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(f)

def draw_mono_text(hdc, x, y, w, h, text, color, font_size):
    gdi32.SetBkMode(hdc, TRANSPARENT)
    gdi32.SetTextColor(hdc, color)
    f = gdi32.CreateFontW(font_size, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Consolas')
    o = gdi32.SelectObject(hdc, f)
    r = RECT(x, y, x+w, y+h)
    user32.DrawTextW(hdc, text, -1, ctypes.byref(r), DT_VCENTER)
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(f)

# ── Drawing ──

def draw_icon(hdc, x, y, accent_color):
    # Icon container with accent-tinted background
    draw_rounded_rect_filled(hdc, x, y, ICON_SZ, ICON_SZ, 10, ICON_BG)
    # Icon symbol
    draw_text_centered(hdc, x, y, ICON_SZ, ICON_SZ, icon_symbol, accent_color, -14, 700)

def draw_eyebrow(hdc, x, y, w, accent_color):
    # Status dot
    dot_brush = gdi32.CreateSolidBrush(accent_color)
    old_b = gdi32.SelectObject(hdc, dot_brush)
    old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
    gdi32.Ellipse(hdc, x, y+2, x+7, y+9)
    gdi32.SelectObject(hdc, old_b)
    gdi32.SelectObject(hdc, old_p)
    gdi32.DeleteObject(dot_brush)
    # Label
    draw_text_left(hdc, x+11, y, w-11, 14, eyebrow, MID_GRAY, -12, 400)

def draw_close_btn(hdc, x, y):
    draw_text_centered(hdc, x, y, 28, 28, "\\u00d7", MID_GRAY, -16, 400)
    btn_close_rect[:] = [x, y, x+28, y+28]

def draw_primary_btn(hdc, x, y, w):
    draw_rounded_rect_filled(hdc, x, y, w, BTN_H, BTN_RADIUS, ACCENT)
    draw_text_centered(hdc, x, y, w, BTN_H, primary_text, LIGHT, -12, 600)
    btn_primary_rect[:] = [x, y, x+w, y+BTN_H]

def draw_ghost_btn(hdc, x, y, w, text):
    draw_rounded_rect_filled(hdc, x, y, w, BTN_H, BTN_RADIUS, GHOST_BG)
    draw_text_centered(hdc, x, y, w, BTN_H, text, TEXT_PRIMARY, -12, 400)
    btn_secondary_rect[:] = [x, y, x+w, y+BTN_H]

def draw_compact(hdc, w, h):
    # Background
    fill_bg(hdc, w, h, BG)

    # Icon
    icon_x = PAD
    icon_y = 20
    draw_icon(hdc, icon_x, icon_y, ACCENT)

    # Eyebrow
    text_x = PAD + ICON_SZ + ICON_TEXT_GAP
    text_w = w - text_x - PAD - 30
    draw_eyebrow(hdc, text_x, 20, text_w, ACCENT)

    # Close button
    draw_close_btn(hdc, w - 28 - 8, 8)

    # Title
    draw_text_left(hdc, text_x, 38, text_w, 20, title, TEXT_PRIMARY, -15, 650)

    # Description
    if desc:
        draw_text_left(hdc, text_x, 58, text_w, 20, desc, TEXT_SECONDARY, -13, 400)

    # Buttons
    btn_y = h - PAD - BTN_H
    px = w - PAD - PRIMARY_BTN_W
    draw_primary_btn(hdc, px, btn_y, PRIMARY_BTN_W)

    # Ghost button text depends on state and detail availability
    ghost_text = "查看详情" if has_detail else "忽略"
    gx = px - BTN_GAP - GHOST_BTN_W
    draw_ghost_btn(hdc, gx, btn_y, GHOST_BTN_W, ghost_text)


def draw_expanded(hdc, w, h):
    # Background
    fill_bg(hdc, w, h, BG)

    # Icon
    icon_x = PAD
    icon_y = 20
    draw_icon(hdc, icon_x, icon_y, ACCENT)

    # Eyebrow
    text_x = PAD + ICON_SZ + ICON_TEXT_GAP
    text_w = w - text_x - PAD - 30
    draw_eyebrow(hdc, text_x, 20, text_w, ACCENT)

    # Close button
    draw_close_btn(hdc, w - 28 - 8, 8)

    # Title
    draw_text_left(hdc, text_x, 38, text_w, 20, title, TEXT_PRIMARY, -15, 650)

    # Description
    if desc:
        draw_text_left(hdc, text_x, 58, text_w, 20, desc, TEXT_SECONDARY, -13, 400)

    # Detail panel
    dy = 82
    panel_w = w - PAD * 2
    draw_rounded_rect_filled(hdc, PAD, dy, panel_w, 60, 10, BG_ELEVATED)

    # Detail content - real data or fallback
    detail_x = PAD + 10
    detail_w = panel_w - 20
    draw_text_left(hdc, detail_x, dy+6, detail_w, 16, "将执行以下操作", TEXT_PRIMARY, -12, 600)

    if tool_name:
        draw_text_left(hdc, detail_x, dy+24, detail_w, 16, tool_name, TEXT_SECONDARY, -12, 400)
    elif cmd_text:
        draw_mono_text(hdc, detail_x, dy+24, detail_w, 16, cmd_text, ACCENT, -12)
    elif proj_path:
        draw_text_left(hdc, detail_x, dy+24, detail_w, 16, proj_path, TEXT_SECONDARY, -12, 400)
    else:
        # Fallback when no detail data
        draw_text_left(hdc, detail_x, dy+24, detail_w, 16, DETAIL_FALLBACK, MID_GRAY, -12, 400)

    # Buttons
    btn_y = h - PAD - BTN_H
    px = w - PAD - PRIMARY_BTN_W
    draw_primary_btn(hdc, px, btn_y, PRIMARY_BTN_W)

    # Expanded: show "收起" instead of "查看详情"
    gx = px - BTN_GAP - GHOST_BTN_W
    draw_ghost_btn(hdc, gx, btn_y, GHOST_BTN_W, "收起")


def draw_pill(hdc, w, h):
    fill_bg(hdc, w, h, BG_ELEVATED)
    dot_brush = gdi32.CreateSolidBrush(ACCENT)
    old_b = gdi32.SelectObject(hdc, dot_brush)
    old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
    gdi32.Ellipse(hdc, 14, 14, 22, 22)
    gdi32.SelectObject(hdc, old_b)
    gdi32.SelectObject(hdc, old_p)
    gdi32.DeleteObject(dot_brush)
    draw_text_left(hdc, 28, 0, w-38, h, eyebrow, MID_GRAY, -12, 400)
    btn_pill_rect[:] = [0, 0, w, h]


def paint(hwnd):
    ps = PS()
    hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
    rc = RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rc))
    w = rc.right
    h = rc.bottom
    if state == "compact":
        draw_compact(hdc, w, h)
    elif state == "expanded":
        draw_expanded(hdc, w, h)
    elif state == "pill":
        draw_pill(hdc, w, h)
    user32.EndPaint(hwnd, ctypes.byref(ps))


# ── State transitions via PostMessage ──
WM_COLLAPSE = 0x0400 + 100
WM_EXPAND = 0x0400 + 101
WM_RESTORE = 0x0400 + 102

def _resize_window(new_state, w, h):
    global state
    state = new_state
    hwnd = hwnd_ref[0]
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    user32.MoveWindow(hwnd, sw - w - 24, sh - h - 60, w, h, True)
    user32.InvalidateRect(hwnd, None, True)


def wp(h, ms, wp, lp):
    if ms == 0x000F:  # WM_PAINT
        paint(h)
        return 0
    elif ms == 0x0014:  # WM_ERASEBKGND
        return 1
    elif ms == 0x0201:  # WM_LBUTTONDOWN
        x = lp & 0xFFFF
        y = (lp >> 16) & 0xFFFF
        if state == "pill":
            user32.PostMessageW(h, WM_RESTORE, 0, 0)
            return 0
        if pt_in_rect(x, y, btn_close_rect):
            user32.DestroyWindow(h)
            return 0
        if pt_in_rect(x, y, btn_primary_rect):
            user32.DestroyWindow(h)
            return 0
        if pt_in_rect(x, y, btn_secondary_rect):
            if state == "expanded":
                # "收起" -> back to compact
                user32.PostMessageW(h, WM_RESTORE, 0, 0)
            elif state == "compact" and has_detail:
                # "查看详情" -> expand
                user32.PostMessageW(h, WM_EXPAND, 0, 0)
            else:
                # "忽略" -> dismiss
                user32.DestroyWindow(h)
            return 0
        return 0
    elif ms == 0x0200:  # WM_MOUSEMOVE
        x = lp & 0xFFFF
        y = (lp >> 16) & 0xFFFF
        in_btn = pt_in_rect(x, y, btn_primary_rect) or pt_in_rect(x, y, btn_secondary_rect) or pt_in_rect(x, y, btn_close_rect) or pt_in_rect(x, y, btn_pill_rect)
        IDC_ARROW = 32512
        IDC_HAND = 32649
        user32.SetCursor(user32.LoadCursorW(0, IDC_HAND if in_btn else IDC_ARROW))
        return 0
    elif ms == 0x0020:  # WM_SETCURSOR
        user32.SetCursor(user32.LoadCursorW(0, 32512))
        return 1
    elif ms == 0x0113:  # WM_TIMER
        if state != "pill":
            user32.PostMessageW(h, WM_COLLAPSE, 0, 0)
        return 0
    elif ms == WM_COLLAPSE:
        _resize_window("pill", PILL_W, PILL_H)
        return 0
    elif ms == WM_EXPAND:
        _resize_window("expanded", EXPANDED_W, EXPANDED_H)
        return 0
    elif ms == WM_RESTORE:
        _resize_window("compact", COMPACT_W, COMPACT_H)
        user32.SetTimer(h, 1, {auto_collapse_ms}, None)
        return 0
    elif ms == 0x0002:  # WM_DESTROY
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(h, ms, wp, lp)

# Sound
def _play():
    try: winsound.PlaySound('SystemNotification', winsound.SND_ALIAS)
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
w.bg = gdi32.CreateSolidBrush(BG)
user32.RegisterClassW(ctypes.byref(w))

sw = user32.GetSystemMetrics(0)
sh = user32.GetSystemMetrics(1)

ex = 0x00000008 | 0x00000080 | 0x08000000
h = user32.CreateWindowExW(ex, 'ClaudeToast', 'AgentBell', 0x80000000,
    sw - COMPACT_W - 24, sh - COMPACT_H - 60, COMPACT_W, COMPACT_H, 0, 0, 0, None)
hwnd_ref[0] = h
user32.ShowWindow(h, 5)
user32.SetWindowPos(h, -1, sw - COMPACT_W - 24, sh - COMPACT_H - 60, COMPACT_W, COMPACT_H, 0x0010 | 0x0040)
user32.UpdateWindow(h)
user32.SetTimer(h, 1, {auto_collapse_ms}, None)

msg = ctypes.wintypes.MSG()
while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0):
    user32.TranslateMessage(ctypes.byref(msg))
    user32.DispatchMessageW(ctypes.byref(msg))
'''


# ── Toast registry ───────────────────────────────────────────────────────────
_TOAST_DIR = os.path.join(tempfile.gettempdir(), "agentbell_toasts")
os.makedirs(_TOAST_DIR, exist_ok=True)


def _cleanup_old_toasts():
    now = time.time()
    for f in os.listdir(_TOAST_DIR):
        path = os.path.join(_TOAST_DIR, f)
        try:
            if now - os.path.getmtime(path) > 30:
                os.unlink(path)
        except OSError:
            pass


def _get_active_toast_count() -> int:
    _cleanup_old_toasts()
    return len([f for f in os.listdir(_TOAST_DIR) if f.endswith(".toast")])


def _register_toast(toast_id: str) -> str:
    marker = os.path.join(_TOAST_DIR, f"{toast_id}.toast")
    with open(marker, "w") as f:
        f.write(str(time.time()))
    return marker


def _unregister_toast(marker_path: str) -> None:
    try:
        os.unlink(marker_path)
    except OSError:
        pass


def show_toast(
    event: ClaudeHookToastEvent,
    config: AgentBellConfig | None = None,
    duration: int = 12,
) -> None:
    cfg = config or AgentBellConfig()
    logger.info("Showing toast: type=%r, title=%r", event.type, event.title)

    # Log the event for debugging
    _log_event(event)

    _cleanup_old_toasts()
    for f in os.listdir(_TOAST_DIR):
        if f.endswith(".toast"):
            marker = os.path.join(_TOAST_DIR, f)
            try:
                mtime = os.path.getmtime(marker)
                if time.time() - mtime < cfg.dedupe_window_ms / 1000:
                    if event.type in f:
                        logger.info("Dedup: skipping %s", event.type)
                        return
            except OSError:
                pass

    active = _get_active_toast_count()
    if active >= cfg.max_visible_toasts:
        logger.info("Max toasts reached (%d)", cfg.max_visible_toasts)
        return

    toast_id = f"{event.type}_{event.id}"
    marker_path = _register_toast(toast_id)

    script = _generate_toast_script(event, cfg)

    y_offset = active * (140 + 8)
    script = script.replace(
        f"sh - COMPACT_H - 60",
        f"sh - COMPACT_H - 60 - {y_offset}"
    ).replace(
        f"sh - PILL_H - 60",
        f"sh - PILL_H - 60 - {y_offset}"
    ).replace(
        f"sh - EXPANDED_H - 60",
        f"sh - EXPANDED_H - 60 - {y_offset}"
    )

    script_path = os.path.join(tempfile.gettempdir(), f"agentbell_toast_{uuid.uuid4().hex[:8]}.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

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
        logger.info("Toast launched.")
    except Exception as e:
        logger.error("Failed to launch toast: %s", e)

    def cleanup():
        time.sleep(duration + 2)
        try:
            os.unlink(script_path)
        except OSError:
            pass
        _unregister_toast(marker_path)

    threading.Thread(target=cleanup, daemon=True).start()


def _log_event(event: ClaudeHookToastEvent) -> None:
    """Log hook event to JSONL file for debugging."""
    import json
    log_dir = os.path.join(os.path.expanduser("~"), ".agentbell", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "hook-events.jsonl")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            record = {
                "timestamp": event.timestamp,
                "type": event.type,
                "title": event.title,
                "message": event.message,
                "tool_name": event.tool_name,
                "command": event.command,
                "project_path": event.project_path,
                "session_id": event.session_id,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def show_permission_toast(
    title: str | None = None,
    message: str | None = None,
    tool_name: str | None = None,
    command: str | None = None,
    project_path: str | None = None,
    config: AgentBellConfig | None = None,
) -> None:
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
    event = ClaudeHookToastEvent(
        id=uuid.uuid4().hex[:12],
        type="task_done",
        title=title,
        message=message,
    )
    show_toast(event, config)
