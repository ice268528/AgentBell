"""Claude-styled toast notification.

Auto-dismisses after 8 seconds. No mini-pill.
Shows session label when available.
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
    GREEN,
    LIGHT,
    MID_GRAY,
    RED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TOAST_BG,
    TOAST_BG_ELEVATED,
    AgentBellConfig,
    ClaudeHookToastEvent,
)

logger = setup_logging()

NULL_PEN = 8
TRANSPARENT = 1
DT_CENTER = 1
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
_TEXT_PRIMARY_BGR = _hex_to_bgr(TEXT_PRIMARY)
_TEXT_SECONDARY_BGR = _hex_to_bgr(TEXT_SECONDARY)
_MID_GRAY_BGR = _hex_to_bgr(MID_GRAY)
_LIGHT_BGR = _hex_to_bgr(LIGHT)
_GREEN_BGR = _hex_to_bgr(GREEN)
_RED_BGR = _hex_to_bgr(RED)

_GHOST_BG = 0x001A1917
_GREEN_ICON_BG = 0x00171E18
_ORANGE_ICON_BG = 0x001E2A29
_BLUE_ICON_BG = 0x00292A1E  # 蓝色图标背景
_RED_ICON_BG = 0x005050C7  # 红色图标背景
_GRAY_ICON_BG = 0x001A1917  # 灰色图标背景

# Toast auto-dismiss in ms
TOAST_DISMISS_MS = 8000


def _generate_toast_script(
    title: str,
    desc: str,
    eyebrow: str,
    icon_symbol: str,
    accent_bgr: int,
    icon_bg_bgr: int,
    has_detail: bool,
    session_label: str = "",
    tool_name: str = "",
    command: str = "",
    project_path: str = "",
    dismiss_ms: int = TOAST_DISMISS_MS,
) -> str:
    """Generate the Python script for a toast window."""

    return f'''import ctypes, ctypes.wintypes, sys, time, winsound, threading, math

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

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_=[('biSize',ctypes.c_uint32),('biWidth',ctypes.c_long),('biHeight',ctypes.c_long),
              ('biPlanes',ctypes.c_uint16),('biBitCount',ctypes.c_uint16),
              ('biCompression',ctypes.c_uint32),('biSizeImage',ctypes.c_uint32),
              ('biXPelsPerMeter',ctypes.c_long),('biYPelsPerMeter',ctypes.c_long),
              ('biClrUsed',ctypes.c_uint32),('biClrImportant',ctypes.c_uint32)]

NULL_PEN = 8
TRANSPARENT = 1
DT_CENTER = 1
DT_VCENTER = 4
SRCCOPY = 0x00CC0020

BG = {_BG}
BG_ELEVATED = {_BG_ELEVATED}
ACCENT = {accent_bgr}
TEXT_PRIMARY = {_TEXT_PRIMARY_BGR}
TEXT_SECONDARY = {_TEXT_SECONDARY_BGR}
MID_GRAY = {_MID_GRAY_BGR}
LIGHT = {_LIGHT_BGR}
GHOST_BG = {_GHOST_BG}
ICON_BG = {icon_bg_bgr}

title = "{_esc(title)}"
desc = "{_esc(desc)}"
eyebrow = "{_esc(eyebrow)}"
icon_symbol = "{icon_symbol}"
session_label = "{_esc(session_label)}"
tool_name = "{_esc(tool_name)}"
cmd_text = "{_esc(command)}"
proj_path = "{_esc(project_path)}"
has_detail = {"True" if has_detail else "False"}
dismiss_ms = {dismiss_ms}

DETAIL_FALLBACK = "工具调用详情暂不可用"

state = "compact"
hwnd_ref = [0]

# Shadow extends window by SHADOW_EXTEND pixels on each side
SHADOW_EXTEND = 20
COMPACT_W, COMPACT_H = 420, 120
EXPANDED_W, EXPANDED_H = 420, 200
# Total window includes shadow area
TOTAL_COMPACT_W = COMPACT_W + SHADOW_EXTEND * 2
TOTAL_COMPACT_H = COMPACT_H + SHADOW_EXTEND * 2
TOTAL_EXPANDED_W = EXPANDED_W + SHADOW_EXTEND * 2
TOTAL_EXPANDED_H = EXPANDED_H + SHADOW_EXTEND * 2
PAD = 12
ICON_SZ = 36
ICON_TEXT_GAP = 12
BTN_H = 28
BTN_RADIUS = 8
BTN_GAP = 8
WINDOW_RADIUS = 12

btn_action_rect = [0, 0, 0, 0]
btn_detail_rect = [0, 0, 0, 0]
btn_close_rect = [0, 0, 0, 0]

ORANGE_ACCENT_BGR = 0x005777D9
ORANGE_ACCENT_BG = 0x00876633
RED_BGR = {_RED_BGR}
RED_ACCENT_BG = 0x005050c7

def pt_in_rect(px, py, r):
    return r[0] <= px <= r[2] and r[1] <= py <= r[3]

def fill_bg(hdc, w, h, color):
    brush = gdi32.CreateSolidBrush(color)
    rc = RECT(0, 0, w, h)
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

def draw_shadow_and_bg(hdc, total_w, total_h, content_w, content_h):
    """Draw multi-layer shadow then rounded background. Shadow is visible outside the rounded rect."""
    # Shadow: draw from outermost to innermost
    for i in range(8, 0, -1):
        off = i * 3
        # Shadow color: darker near window, lighter far away
        intensity = int(8 + (8 - i) * 4)  # 8..36 (darker shadow)
        sc = (intensity << 16) | (intensity << 8) | intensity
        brush = gdi32.CreateSolidBrush(sc)
        old_b = gdi32.SelectObject(hdc, brush)
        old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
        gdi32.RoundRect(hdc, SHADOW_EXTEND - off, SHADOW_EXTEND - off,
                        SHADOW_EXTEND + content_w + off, SHADOW_EXTEND + content_h + off,
                        WINDOW_RADIUS + off, WINDOW_RADIUS + off)
        gdi32.SelectObject(hdc, old_b)
        gdi32.SelectObject(hdc, old_p)
        gdi32.DeleteObject(brush)
    # Main rounded background
    draw_rounded_rect_filled(hdc, SHADOW_EXTEND, SHADOW_EXTEND, content_w, content_h, WINDOW_RADIUS, BG)

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

def draw_icon(hdc, x, y, size=ICON_SZ):
    draw_rounded_rect_filled(hdc, x, y, size, size, 8, ICON_BG)
    draw_text_centered(hdc, x, y, size, size, icon_symbol, RED_BGR, -14, 700)

def draw_eyebrow(hdc, x, y, w):
    dot_brush = gdi32.CreateSolidBrush(ACCENT)
    old_b = gdi32.SelectObject(hdc, dot_brush)
    old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
    gdi32.Ellipse(hdc, x, y+2, x+5, y+7)
    gdi32.SelectObject(hdc, old_b)
    gdi32.SelectObject(hdc, old_p)
    gdi32.DeleteObject(dot_brush)
    label = eyebrow
    if session_label:
        label = eyebrow + " · " + session_label
    draw_text_left(hdc, x+8, y, w-8, 12, label, MID_GRAY, -10, 400)

def draw_close_btn(hdc, x, y):
    draw_text_centered(hdc, x, y, 22, 22, "\\u00d7", MID_GRAY, -12, 400)
    btn_close_rect[:] = [x, y, x+22, y+22]

def draw_ghost_btn(hdc, x, y, w, text, rect_store):
    draw_rounded_rect_filled(hdc, x, y, w, BTN_H, BTN_RADIUS, GHOST_BG)
    draw_text_centered(hdc, x, y, w, BTN_H, text, TEXT_PRIMARY, -10, 400)
    rect_store[:] = [x, y, x+w, y+BTN_H]

def draw_orange_btn(hdc, x, y, w, text, rect_store):
    """Draw Soft Red primary action button."""
    draw_rounded_rect_filled(hdc, x, y, w, BTN_H, BTN_RADIUS, RED_ACCENT_BG)
    draw_text_centered(hdc, x, y, w, BTN_H, text, TEXT_PRIMARY, -12, 600)
    rect_store[:] = [x, y, x+w, y+BTN_H]

def draw_header_and_body(hdc, content_w):
    """Wide layout: icon left, text center, buttons right."""
    S = SHADOW_EXTEND
    # Icon (large, left side)
    icon_x = S + PAD
    icon_y = S + PAD + 2
    draw_icon(hdc, icon_x, icon_y, ICON_SZ)

    # Text area (center, after icon)
    text_x = icon_x + ICON_SZ + ICON_TEXT_GAP
    text_right = S + content_w - PAD - 90  # leave room for buttons
    text_w = text_right - text_x

    # Eyebrow (status dot + label)
    draw_eyebrow(hdc, text_x, S + PAD + 4, text_w)

    # Title (bold)
    draw_text_left(hdc, text_x, S + PAD + 18, text_w, 18, title, TEXT_PRIMARY, -13, 650)

    # Description
    if desc:
        draw_text_left(hdc, text_x, S + PAD + 36, text_w, 14, desc, TEXT_SECONDARY, -11, 400)

    # Project pill
    pill_text = session_label or ""
    if pill_text:
        pill_w = max(40, len(pill_text) * 7 + 12)
        pill_x = text_x
        pill_y = S + PAD + 52
        pill_h = 18
        pill_pen = gdi32.CreatePen(1, 1, MID_GRAY)
        old_pen = gdi32.SelectObject(hdc, pill_pen)
        old_brush2 = gdi32.SelectObject(hdc, gdi32.GetStockObject(4))
        gdi32.RoundRect(hdc, pill_x, pill_y, pill_x + pill_w, pill_y + pill_h, 5, 5)
        gdi32.SelectObject(hdc, old_pen)
        gdi32.SelectObject(hdc, old_brush2)
        gdi32.DeleteObject(pill_pen)
        draw_text_centered(hdc, pill_x, pill_y, pill_w, pill_h, pill_text, MID_GRAY, -9, 400)

    # Close button (top right)
    draw_close_btn(hdc, S + content_w - 28, S + 6)

    # Buttons (right side, vertically centered)
    btn_x = S + content_w - PAD - 80
    btn_center_y = S + content_h // 2 - BTN_H // 2
    if has_detail:
        draw_orange_btn(hdc, btn_x, btn_center_y - BTN_H - BTN_GAP // 2, 80, "我知道了", btn_action_rect)
        draw_ghost_btn(hdc, btn_x, btn_center_y + BTN_GAP // 2, 80, "查看详情", btn_detail_rect)
    else:
        draw_orange_btn(hdc, btn_x, btn_center_y, 80, "我知道了", btn_action_rect)

def draw_compact(hdc, total_w, total_h):
    content_w, content_h = COMPACT_W, COMPACT_H
    draw_shadow_and_bg(hdc, total_w, total_h, content_w, content_h)
    draw_header_and_body(hdc, content_w)

def draw_expanded(hdc, total_w, total_h):
    content_w, content_h = EXPANDED_W, EXPANDED_H
    draw_shadow_and_bg(hdc, total_w, total_h, content_w, content_h)
    draw_header_and_body(hdc, content_w)
    S = SHADOW_EXTEND
    dy = S + 80
    panel_w = content_w - PAD * 2
    draw_rounded_rect_filled(hdc, S + PAD, dy, panel_w, 50, 6, BG_ELEVATED)
    detail_x = S + PAD + 12
    detail_w = panel_w - 24
    draw_text_left(hdc, detail_x, dy+6, detail_w, 14, "将执行以下操作", TEXT_PRIMARY, -11, 600)
    if tool_name:
        draw_text_left(hdc, detail_x, dy+22, detail_w, 14, tool_name, TEXT_SECONDARY, -11, 400)
    elif cmd_text:
        draw_mono_text(hdc, detail_x, dy+22, detail_w, 14, cmd_text, ACCENT, -11)
    elif proj_path:
        draw_text_left(hdc, detail_x, dy+22, detail_w, 14, proj_path, TEXT_SECONDARY, -11, 400)
    else:
        draw_text_left(hdc, detail_x, dy+22, detail_w, 14, DETAIL_FALLBACK, MID_GRAY, -11, 400)
    # Buttons at bottom right
    btn_x = S + content_w - PAD - 80
    btn_y = S + content_h - PAD - BTN_H
    draw_orange_btn(hdc, btn_x, btn_y, 80, "我知道了", btn_action_rect)
    draw_ghost_btn(hdc, btn_x - BTN_GAP - 80, btn_y, 80, "收起", btn_detail_rect)

def paint(hwnd):
    ps = PS()
    hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
    rc = RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rc))
    tw, th = rc.right, rc.bottom
    # Clear entire window to transparent (black)
    fill_bg(hdc, tw, th, 0x00000000)
    if state == "compact":
        draw_compact(hdc, tw, th)
    elif state == "expanded":
        draw_expanded(hdc, tw, th)
    user32.EndPaint(hwnd, ctypes.byref(ps))

WM_EXPAND = 0x0400 + 101
WM_RESTORE = 0x0400 + 102

def _resize_window(new_state, w, h):
    global state
    state = new_state
    hwnd = hwnd_ref[0]
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    # Add shadow extend to total window size
    tw = w + SHADOW_EXTEND * 2
    th = h + SHADOW_EXTEND * 2
    user32.MoveWindow(hwnd, sw - tw - 24, sh - th - 60, tw, th, True)
    user32.InvalidateRect(hwnd, None, True)

def wp(h, ms, wp, lp):
    if ms == 0x000F:
        paint(h)
        return 0
    elif ms == 0x0014:
        return 1
    elif ms == 0x0201:
        x = lp & 0xFFFF
        y = (lp >> 16) & 0xFFFF
        if pt_in_rect(x, y, btn_close_rect):
            user32.DestroyWindow(h)
            return 0
        if pt_in_rect(x, y, btn_action_rect):
            user32.DestroyWindow(h)
            return 0
        if pt_in_rect(x, y, btn_detail_rect):
            if state == "expanded":
                user32.PostMessageW(h, WM_RESTORE, 0, 0)
            elif state == "compact" and has_detail:
                user32.PostMessageW(h, WM_EXPAND, 0, 0)
            return 0
        return 0
    elif ms == 0x0200:
        x = lp & 0xFFFF
        y = (lp >> 16) & 0xFFFF
        in_btn = pt_in_rect(x, y, btn_action_rect) or pt_in_rect(x, y, btn_detail_rect) or pt_in_rect(x, y, btn_close_rect)
        IDC_ARROW = 32512
        IDC_HAND = 32649
        user32.SetCursor(user32.LoadCursorW(0, IDC_HAND if in_btn else IDC_ARROW))
        return 0
    elif ms == 0x0020:
        user32.SetCursor(user32.LoadCursorW(0, 32512))
        return 1
    elif ms == 0x0113:  # WM_TIMER -> auto dismiss
        user32.DestroyWindow(h)
        return 0
    elif ms == WM_EXPAND:
        _resize_window("expanded", EXPANDED_W, EXPANDED_H)
        return 0
    elif ms == WM_RESTORE:
        _resize_window("compact", COMPACT_W, COMPACT_H)
        user32.SetTimer(h, 1, dismiss_ms, None)
        return 0
    elif ms == 0x0002:
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(h, ms, wp, lp)

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

# WS_EX_LAYERED for per-pixel alpha transparency (needed for shadow)
WS_EX_LAYERED = 0x00080000
ex = 0x00000008 | 0x00000080 | 0x08000000 | WS_EX_LAYERED
# Window includes shadow area
tw = COMPACT_W + SHADOW_EXTEND * 2
th = COMPACT_H + SHADOW_EXTEND * 2
h = user32.CreateWindowExW(ex, 'ClaudeToast', 'AgentBell', 0x80000000,
    sw - tw - 24, sh - th - 60, tw, th, 0, 0, 0, None)
hwnd_ref[0] = h

# Set layered window attributes: black = transparent, white = opaque
user32.SetLayeredWindowAttributes(h, 0x00000000, 0, 0x00000001)  # LWA_COLORKEY

user32.ShowWindow(h, 5)
user32.SetWindowPos(h, -1, sw - tw - 24, sh - th - 60, tw, th, 0x0010 | 0x0040)
user32.UpdateWindow(h)
user32.SetTimer(h, 1, dismiss_ms, None)

msg = ctypes.wintypes.MSG()
while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0):
    user32.TranslateMessage(ctypes.byref(msg))
    user32.DispatchMessageW(ctypes.byref(msg))
'''


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


def _dismiss_oldest_toast() -> None:
    """关闭最旧的 toast，为新 toast 腾出空间"""
    try:
        toasts = []
        for f in os.listdir(_TOAST_DIR):
            if f.endswith(".toast"):
                path = os.path.join(_TOAST_DIR, f)
                try:
                    mtime = os.path.getmtime(path)
                    toasts.append((mtime, path))
                except OSError:
                    pass
        if toasts:
            # 按时间排序，删除最旧的
            toasts.sort(key=lambda x: x[0])
            oldest_path = toasts[0][1]
            os.unlink(oldest_path)
            logger.info("Dismissed oldest toast: %s", os.path.basename(oldest_path))
    except Exception as e:
        logger.error("Failed to dismiss oldest toast: %s", e)


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
    session_label: str = "",
    duration: int = 12,
) -> None:
    """Show a toast notification."""
    cfg = config or AgentBellConfig()
    logger.info("Showing toast: type=%r, title=%r, session=%r", event.type, event.title, session_label)
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
        # 关闭最旧的 toast，为新 toast 腾出空间
        _dismiss_oldest_toast()

    toast_id = f"{event.type}_{event.id}"
    marker_path = _register_toast(toast_id)

    # Resolve display values
    is_done = event.type == "task_done"
    is_error = event.type == "error"
    is_waiting_input = event.type == "waiting_input"

    # 根据事件类型选择不同的颜色
    if is_done:
        accent_bgr = _GREEN_BGR
        icon_bg_bgr = _GREEN_ICON_BG
    elif is_error:
        accent_bgr = _hex_to_bgr("#c75050")
        icon_bg_bgr = _RED_ICON_BG
    elif is_waiting_input:
        accent_bgr = _hex_to_bgr("#6a9bcc")  # 蓝色 - 等待输入
        icon_bg_bgr = _BLUE_ICON_BG
    else:
        accent_bgr = _ACCENT  # 橙色 - 等待授权
        icon_bg_bgr = _ORANGE_ICON_BG

    title = event.title or {
        "permission_required": "Claude Code 需要授权",
        "task_done": "Claude Code 任务完成",
        "error": "Claude Code 执行失败",
        "info": "Claude Code 通知",
        "waiting_input": "Claude Code 等待输入",
    }.get(event.type, "Claude Code 通知")

    desc = event.message or {
        "permission_required": "需要你确认工具调用以继续执行。",
        "task_done": "任务已完成。请回到 Claude Code 终端查看输出或继续操作。",
        "error": "执行过程中出现错误。",
        "info": "",
        "waiting_input": "本轮响应已结束，请回到终端继续操作。",
    }.get(event.type, "")

    eyebrow = {
        "permission_required": "等待授权",
        "task_done": "已完成",
        "error": "错误",
        "info": "通知",
        "waiting_input": "等待输入",
    }.get(event.type, "通知")

    icon_symbol = {
        "permission_required": ">_",
        "task_done": "\\u2713",
        "error": "!",
        "info": "i",
        "waiting_input": "\\u23CE",
    }.get(event.type, ">_")

    tool_name = event.tool_name or ""
    command = event.command or ""
    project_path = event.project_path or ""
    has_detail = bool(tool_name or command or project_path)

    script = _generate_toast_script(
        title=title,
        desc=desc,
        eyebrow=eyebrow,
        icon_symbol=icon_symbol,
        accent_bgr=accent_bgr,
        icon_bg_bgr=icon_bg_bgr,
        has_detail=has_detail,
        session_label=session_label,
        tool_name=tool_name,
        command=command,
        project_path=project_path,
        dismiss_ms=cfg.toast_dismiss_ms if hasattr(cfg, 'toast_dismiss_ms') else TOAST_DISMISS_MS,
    )

    y_offset = active * (228 + 8)  # COMPACT_H(180) + SHADOW_EXTEND*2(48) + gap
    script = script.replace(
        "sh - th - 60",
        f"sh - th - 60 - {y_offset}"
    )

    script_path = os.path.join(tempfile.gettempdir(), f"agentbell_toast_{uuid.uuid4().hex[:8]}.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    try:
        proc = subprocess.Popen(
            [pythonw, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        logger.info("Toast launched: pid=%s, script=%s", proc.pid, os.path.basename(script_path))
    except Exception as e:
        logger.error("Failed to launch toast with %s: %s", pythonw, e)
        # Fallback: try sys.executable directly
        try:
            proc = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=0x08000000,
            )
            logger.info("Toast launched via fallback: pid=%s", proc.pid)
        except Exception as e2:
            logger.error("Fallback also failed: %s", e2)

    def cleanup():
        time.sleep(duration + 2)
        try:
            # Check if subprocess had errors
            if proc and proc.poll() is not None:
                stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
                if stderr:
                    logger.warning("Toast subprocess stderr: %s", stderr[:500])
        except Exception:
            pass
        try:
            os.unlink(script_path)
        except OSError:
            pass
        _unregister_toast(marker_path)

    threading.Thread(target=cleanup, daemon=True).start()


def _log_event(event: ClaudeHookToastEvent) -> None:
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


def show_permission_toast(title=None, message=None, tool_name=None, command=None, project_path=None, config=None, session_label=""):
    event = ClaudeHookToastEvent(id=uuid.uuid4().hex[:12], type="permission_required",
        title=title, message=message, tool_name=tool_name, command=command, project_path=project_path)
    show_toast(event, config, session_label=session_label)


def show_done_toast(title=None, message=None, config=None, session_label=""):
    event = ClaudeHookToastEvent(id=uuid.uuid4().hex[:12], type="task_done", title=title, message=message)
    show_toast(event, config, session_label=session_label)
