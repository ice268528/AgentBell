"""Persistent toast daemon process.

Listens on Windows Named Pipe and manages toast windows in a single
long-lived process, avoiding the ~50ms Python startup cost on every toast.
"""

import ctypes
import ctypes.wintypes
import json
import logging
import sys
import threading
import time
import winsound

from agentbell.theme import (
    ACCENT_PRIMARY,
    GREEN,
    LIGHT,
    MID_GRAY,
    RED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TOAST_BG,
    TOAST_BG_ELEVATED,
)

logger = logging.getLogger("agentbell.toast_daemon")

# ── Pipe constants ───────────────────────────────────────────────────────────
PIPE_NAME = chr(92)*2 + "." + chr(92) + "pipe" + chr(92) + "agentbell_toast"
PIPE_BUFFER_SIZE = 4096
PIPE_MAX_INSTANCES = 1

# ── Win32 constants ──────────────────────────────────────────────────────────
NULL_PEN = 8
TRANSPARENT = 1
DT_CENTER = 1
DT_VCENTER = 4
DT_SINGLELINE = 0x20
CREATE_NO_WINDOW = 0x08000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# Named pipe constants
PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_BYTE = 0x00000000
PIPE_READMODE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000
ERROR_MORE_DATA = 234
ERROR_BROKEN_PIPE = 109

# Window constants
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_LAYERED = 0x00080000
WS_POPUP = 0x80000000
SW_SHOWNOACTIVATE = 5
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
LWA_COLORKEY = 0x00000001
WM_PAINT = 0x000F
WM_ERASEBKGND = 0x0014
WM_LBUTTONDOWN = 0x0201
WM_MOUSEMOVE = 0x0200
WM_SETCURSOR = 0x0020
WM_TIMER = 0x0113
WM_DESTROY = 0x0002
WM_USER = 0x0400
WM_EXPAND = WM_USER + 101
WM_RESTORE = WM_USER + 102
IDC_ARROW = 32512
IDC_HAND = 32649
TOAST_DISMISS_MS = 8000

# ── Theme BGR ────────────────────────────────────────────────────────────────


def _hex_to_bgr(hex_color: str) -> int:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


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
_BLUE_ICON_BG = 0x00292A1E
_RED_ICON_BG = 0x005050C7
_GRAY_ICON_BG = 0x001A1917

# ── Toast geometry ───────────────────────────────────────────────────────────
SHADOW_EXTEND = 20
COMPACT_W, COMPACT_H = 420, 120
EXPANDED_W, EXPANDED_H = 420, 200
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

# ── Win32 API setup ──────────────────────────────────────────────────────────
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

LRESULT = ctypes.c_longlong if sys.maxsize > 2**32 else ctypes.c_long
LP = ctypes.c_longlong if sys.maxsize > 2**32 else ctypes.c_long
WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT, ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, LP
)
user32.DefWindowProcW.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.c_uint,
    ctypes.wintypes.WPARAM,
    LP,
]
user32.DefWindowProcW.restype = LRESULT

# ── Global state ─────────────────────────────────────────────────────────────
_hwnd_map: dict[int, "ToastWindow"] = {}
_window_class_registered = False
_window_class_name = "ClaudeToastDaemon"
_global_wnd_proc_ref = None  # Keep reference to prevent garbage collection


# ── Win32 structures ─────────────────────────────────────────────────────────
class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", ctypes.c_uint),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.wintypes.HINSTANCE),
        ("hIcon", ctypes.wintypes.HICON),
        ("hCursor", ctypes.wintypes.HANDLE),
        ("hbrBackground", ctypes.wintypes.HANDLE),
        ("lpszMenuName", ctypes.wintypes.LPCWSTR),
        ("lpszClassName", ctypes.wintypes.LPCWSTR),
    ]


class PS(ctypes.Structure):
    _fields_ = [
        ("hdc", ctypes.wintypes.HDC),
        ("fErase", ctypes.wintypes.BOOL),
        ("rc", ctypes.wintypes.RECT),
        ("fR", ctypes.wintypes.BOOL),
        ("fI", ctypes.wintypes.BOOL),
        ("r", ctypes.c_byte * 32),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


# ── Drawing helpers ──────────────────────────────────────────────────────────
def _fill_bg(hdc, w, h, color):
    brush = gdi32.CreateSolidBrush(color)
    rc = RECT(0, 0, w, h)
    user32.FillRect(hdc, ctypes.byref(rc), brush)
    gdi32.DeleteObject(brush)


def _draw_rounded_rect_filled(hdc, x, y, w, h, r, color):
    brush = gdi32.CreateSolidBrush(color)
    old_b = gdi32.SelectObject(hdc, brush)
    old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
    gdi32.RoundRect(hdc, x, y, x + w, y + h, r, r)
    gdi32.SelectObject(hdc, old_b)
    gdi32.SelectObject(hdc, old_p)
    gdi32.DeleteObject(brush)


def _draw_text_centered(hdc, x, y, w, h, text, color, font_size, weight):
    gdi32.SetBkMode(hdc, TRANSPARENT)
    gdi32.SetTextColor(hdc, color)
    f = gdi32.CreateFontW(
        font_size, 0, 0, 0, weight, 0, 0, 0, 0, 0, 0, 0, 0, "Segoe UI"
    )
    o = gdi32.SelectObject(hdc, f)
    r = RECT(x, y, x + w, y + h)
    user32.DrawTextW(
        hdc, text, -1, ctypes.byref(r), DT_CENTER | DT_VCENTER | DT_SINGLELINE
    )
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(f)


def _draw_text_left(hdc, x, y, w, h, text, color, font_size, weight):
    gdi32.SetBkMode(hdc, TRANSPARENT)
    gdi32.SetTextColor(hdc, color)
    f = gdi32.CreateFontW(
        font_size, 0, 0, 0, weight, 0, 0, 0, 0, 0, 0, 0, 0, "Segoe UI"
    )
    o = gdi32.SelectObject(hdc, f)
    r = RECT(x, y, x + w, y + h)
    user32.DrawTextW(hdc, text, -1, ctypes.byref(r), DT_VCENTER)
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(f)


def _draw_mono_text(hdc, x, y, w, h, text, color, font_size):
    gdi32.SetBkMode(hdc, TRANSPARENT)
    gdi32.SetTextColor(hdc, color)
    f = gdi32.CreateFontW(
        font_size, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, "Consolas"
    )
    o = gdi32.SelectObject(hdc, f)
    r = RECT(x, y, x + w, y + h)
    user32.DrawTextW(hdc, text, -1, ctypes.byref(r), DT_VCENTER)
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(f)


# ── ToastWindow ──────────────────────────────────────────────────────────────
class ToastWindow:
    """A single toast notification window."""

    def __init__(self, params: dict, on_destroyed=None):
        self.toast_id = params.get("id", "")
        self.title = params.get("title", "")
        self.desc = params.get("message", "")
        self.eyebrow = params.get("eyebrow", "通知")
        self.icon_symbol = params.get("icon_symbol", ">_")
        self.accent_bgr = params.get("accent_bgr", _ACCENT)
        self.icon_bg_bgr = params.get("icon_bg_bgr", _ORANGE_ICON_BG)
        self.has_detail = params.get("has_detail", False)
        self.session_label = params.get("session_label", "")
        self.tool_name = params.get("tool_name", "")
        self.cmd_text = params.get("command", "")
        self.proj_path = params.get("project_path", "")
        self.dismiss_ms = params.get("dismiss_ms", TOAST_DISMISS_MS)
        self.y_offset = params.get("y_offset", 0)
        self.on_destroyed = on_destroyed

        self.state = "compact"
        self.hwnd = 0
        self._closed = False

        # Button hit-test rectangles
        self.btn_action_rect = [0, 0, 0, 0]
        self.btn_detail_rect = [0, 0, 0, 0]
        self.btn_close_rect = [0, 0, 0, 0]

    def create(self):
        """Create and show the toast window. Runs in a new thread."""
        global _window_class_registered
        if not _window_class_registered:
            self._register_class()
            _window_class_registered = True

        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)

        ex_style = WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_LAYERED
        tw = COMPACT_W + SHADOW_EXTEND * 2
        th = COMPACT_H + SHADOW_EXTEND * 2

        self.hwnd = user32.CreateWindowExW(
            ex_style,
            _window_class_name,
            "AgentBell Toast",
            WS_POPUP,
            sw - tw - 24,
            sh - th - 60 - self.y_offset,
            tw,
            th,
            0,
            0,
            0,
            None,
        )

        if not self.hwnd:
            logger.error("CreateWindowExW failed")
            return

        _hwnd_map[self.hwnd] = self

        user32.SetLayeredWindowAttributes(self.hwnd, 0x00000000, 0, LWA_COLORKEY)
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        user32.SetWindowPos(
            self.hwnd,
            HWND_TOPMOST,
            sw - tw - 24,
            sh - th - 60 - self.y_offset,
            tw,
            th,
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
        user32.UpdateWindow(self.hwnd)
        user32.SetTimer(self.hwnd, 1, self.dismiss_ms, None)

        # Play sound in background
        threading.Thread(target=self._play_sound, daemon=True).start()

        # Message loop
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # Cleanup
        _hwnd_map.pop(self.hwnd, None)
        self._closed = True
        if self.on_destroyed:
            self.on_destroyed(self.toast_id)

    def _register_class(self):
        global _global_wnd_proc_ref
        _global_wnd_proc_ref = WNDPROC(_global_wnd_proc)  # Keep reference

        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = _global_wnd_proc_ref
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = 0
        wc.hIcon = 0
        wc.hCursor = user32.LoadCursorW(0, IDC_ARROW)
        wc.hbrBackground = gdi32.CreateSolidBrush(_BG)
        wc.lpszMenuName = None
        wc.lpszClassName = _window_class_name
        user32.RegisterClassW(ctypes.byref(wc))

    def _play_sound(self):
        try:
            winsound.PlaySound("SystemNotification", winsound.SND_ALIAS)
        except Exception:
            pass

    def wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_PAINT:
            ps = PS()
            hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
            rc = RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rc))
            tw, th = rc.right, rc.bottom
            _fill_bg(hdc, tw, th, 0x00000000)
            if self.state == "compact":
                self._draw_compact(hdc, tw, th)
            elif self.state == "expanded":
                self._draw_expanded(hdc, tw, th)
            user32.EndPaint(hwnd, ctypes.byref(ps))
            return 0

        elif msg == WM_ERASEBKGND:
            return 1

        elif msg == WM_LBUTTONDOWN:
            x = lparam & 0xFFFF
            y = (lparam >> 16) & 0xFFFF
            if self._pt_in_rect(x, y, self.btn_close_rect):
                user32.DestroyWindow(hwnd)
                return 0
            if self._pt_in_rect(x, y, self.btn_action_rect):
                user32.DestroyWindow(hwnd)
                return 0
            if self._pt_in_rect(x, y, self.btn_detail_rect):
                if self.state == "expanded":
                    user32.PostMessageW(hwnd, WM_RESTORE, 0, 0)
                elif self.state == "compact" and self.has_detail:
                    user32.PostMessageW(hwnd, WM_EXPAND, 0, 0)
                return 0
            return 0

        elif msg == WM_MOUSEMOVE:
            x = lparam & 0xFFFF
            y = (lparam >> 16) & 0xFFFF
            in_btn = (
                self._pt_in_rect(x, y, self.btn_action_rect)
                or self._pt_in_rect(x, y, self.btn_detail_rect)
                or self._pt_in_rect(x, y, self.btn_close_rect)
            )
            cursor_id = IDC_HAND if in_btn else IDC_ARROW
            user32.SetCursor(user32.LoadCursorW(0, cursor_id))
            return 0

        elif msg == WM_SETCURSOR:
            user32.SetCursor(user32.LoadCursorW(0, IDC_ARROW))
            return 1

        elif msg == WM_TIMER:
            user32.DestroyWindow(hwnd)
            return 0

        elif msg == WM_EXPAND:
            self._resize_window("expanded", EXPANDED_W, EXPANDED_H)
            return 0

        elif msg == WM_RESTORE:
            self._resize_window("compact", COMPACT_W, COMPACT_H)
            user32.SetTimer(hwnd, 1, self.dismiss_ms, None)
            return 0

        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _pt_in_rect(self, px, py, r):
        return r[0] <= px <= r[2] and r[1] <= py <= r[3]

    def _resize_window(self, new_state, w, h):
        self.state = new_state
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        tw = w + SHADOW_EXTEND * 2
        th = h + SHADOW_EXTEND * 2
        user32.MoveWindow(
            self.hwnd,
            sw - tw - 24,
            sh - th - 60 - self.y_offset,
            tw,
            th,
            True,
        )
        user32.InvalidateRect(self.hwnd, None, True)

    def _draw_shadow_and_bg(self, hdc, total_w, total_h, content_w, content_h):
        for i in range(8, 0, -1):
            off = i * 3
            intensity = int(8 + (8 - i) * 4)
            sc = (intensity << 16) | (intensity << 8) | intensity
            brush = gdi32.CreateSolidBrush(sc)
            old_b = gdi32.SelectObject(hdc, brush)
            old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
            gdi32.RoundRect(
                hdc,
                SHADOW_EXTEND - off,
                SHADOW_EXTEND - off,
                SHADOW_EXTEND + content_w + off,
                SHADOW_EXTEND + content_h + off,
                WINDOW_RADIUS + off,
                WINDOW_RADIUS + off,
            )
            gdi32.SelectObject(hdc, old_b)
            gdi32.SelectObject(hdc, old_p)
            gdi32.DeleteObject(brush)
        _draw_rounded_rect_filled(
            hdc, SHADOW_EXTEND, SHADOW_EXTEND, content_w, content_h, WINDOW_RADIUS, _BG
        )

    def _draw_icon(self, hdc, x, y, size=ICON_SZ):
        _draw_rounded_rect_filled(hdc, x, y, size, size, 8, self.icon_bg_bgr)
        _draw_text_centered(hdc, x, y, size, size, self.icon_symbol, _RED_BGR, -14, 700)

    def _draw_eyebrow(self, hdc, x, y, w):
        dot_brush = gdi32.CreateSolidBrush(self.accent_bgr)
        old_b = gdi32.SelectObject(hdc, dot_brush)
        old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
        gdi32.Ellipse(hdc, x, y + 2, x + 5, y + 7)
        gdi32.SelectObject(hdc, old_b)
        gdi32.SelectObject(hdc, old_p)
        gdi32.DeleteObject(dot_brush)
        label = self.eyebrow
        if self.session_label:
            label = self.eyebrow + " · " + self.session_label
        _draw_text_left(hdc, x + 8, y, w - 8, 12, label, _MID_GRAY_BGR, -10, 400)

    def _draw_close_btn(self, hdc, x, y):
        _draw_text_centered(hdc, x, y, 22, 22, "×", _MID_GRAY_BGR, -12, 400)
        self.btn_close_rect[:] = [x, y, x + 22, y + 22]

    def _draw_ghost_btn(self, hdc, x, y, w, text, rect_store):
        _draw_rounded_rect_filled(hdc, x, y, w, BTN_H, BTN_RADIUS, _GHOST_BG)
        _draw_text_centered(hdc, x, y, w, BTN_H, text, _TEXT_PRIMARY_BGR, -10, 400)
        rect_store[:] = [x, y, x + w, y + BTN_H]

    def _draw_orange_btn(self, hdc, x, y, w, text, rect_store):
        _draw_rounded_rect_filled(hdc, x, y, w, BTN_H, BTN_RADIUS, 0x005050C7)
        _draw_text_centered(hdc, x, y, w, BTN_H, text, _TEXT_PRIMARY_BGR, -12, 600)
        rect_store[:] = [x, y, x + w, y + BTN_H]

    def _draw_header_and_body(self, hdc, content_w, content_h):
        S = SHADOW_EXTEND
        icon_x = S + PAD
        icon_y = S + PAD + 2
        self._draw_icon(hdc, icon_x, icon_y, ICON_SZ)

        text_x = icon_x + ICON_SZ + ICON_TEXT_GAP
        text_right = S + content_w - PAD - 90
        text_w = text_right - text_x

        self._draw_eyebrow(hdc, text_x, S + PAD + 4, text_w)
        _draw_text_left(
            hdc, text_x, S + PAD + 18, text_w, 18, self.title, _TEXT_PRIMARY_BGR, -13, 650
        )

        if self.desc:
            _draw_text_left(
                hdc,
                text_x,
                S + PAD + 36,
                text_w,
                14,
                self.desc,
                _TEXT_SECONDARY_BGR,
                -11,
                400,
            )

        pill_text = self.session_label or ""
        if pill_text:
            pill_w = max(40, len(pill_text) * 7 + 12)
            pill_x = text_x
            pill_y = S + PAD + 52
            pill_h = 18
            pill_pen = gdi32.CreatePen(1, 1, _MID_GRAY_BGR)
            old_pen = gdi32.SelectObject(hdc, pill_pen)
            old_brush2 = gdi32.SelectObject(hdc, gdi32.GetStockObject(4))
            gdi32.RoundRect(
                hdc, pill_x, pill_y, pill_x + pill_w, pill_y + pill_h, 5, 5
            )
            gdi32.SelectObject(hdc, old_pen)
            gdi32.SelectObject(hdc, old_brush2)
            gdi32.DeleteObject(pill_pen)
            _draw_text_centered(
                hdc, pill_x, pill_y, pill_w, pill_h, pill_text, _MID_GRAY_BGR, -9, 400
            )

        self._draw_close_btn(hdc, S + content_w - 28, S + 6)

        btn_x = S + content_w - PAD - 80
        btn_center_y = S + content_h // 2 - BTN_H // 2
        if self.has_detail:
            self._draw_orange_btn(
                hdc,
                btn_x,
                btn_center_y - BTN_H - BTN_GAP // 2,
                80,
                "我知道了",
                self.btn_action_rect,
            )
            self._draw_ghost_btn(
                hdc,
                btn_x,
                btn_center_y + BTN_GAP // 2,
                80,
                "查看详情",
                self.btn_detail_rect,
            )
        else:
            self._draw_orange_btn(
                hdc, btn_x, btn_center_y, 80, "我知道了", self.btn_action_rect
            )

    def _draw_compact(self, hdc, total_w, total_h):
        content_w, content_h = COMPACT_W, COMPACT_H
        self._draw_shadow_and_bg(hdc, total_w, total_h, content_w, content_h)
        self._draw_header_and_body(hdc, content_w, content_h)

    def _draw_expanded(self, hdc, total_w, total_h):
        content_w, content_h = EXPANDED_W, EXPANDED_H
        self._draw_shadow_and_bg(hdc, total_w, total_h, content_w, content_h)
        self._draw_header_and_body(hdc, content_w, content_h)
        S = SHADOW_EXTEND
        dy = S + 80
        panel_w = content_w - PAD * 2
        _draw_rounded_rect_filled(hdc, S + PAD, dy, panel_w, 50, 6, _BG_ELEVATED)
        detail_x = S + PAD + 12
        detail_w = panel_w - 24
        _draw_text_left(
            hdc, detail_x, dy + 6, detail_w, 14, "将执行以下操作", _TEXT_PRIMARY_BGR, -11, 600
        )
        if self.tool_name:
            _draw_text_left(
                hdc,
                detail_x,
                dy + 22,
                detail_w,
                14,
                self.tool_name,
                _TEXT_SECONDARY_BGR,
                -11,
                400,
            )
        elif self.cmd_text:
            _draw_mono_text(
                hdc, detail_x, dy + 22, detail_w, 14, self.cmd_text, self.accent_bgr, -11
            )
        elif self.proj_path:
            _draw_text_left(
                hdc,
                detail_x,
                dy + 22,
                detail_w,
                14,
                self.proj_path,
                _TEXT_SECONDARY_BGR,
                -11,
                400,
            )
        else:
            _draw_text_left(
                hdc,
                detail_x,
                dy + 22,
                detail_w,
                14,
                "工具调用详情暂不可用",
                _MID_GRAY_BGR,
                -11,
                400,
            )

        btn_x = S + content_w - PAD - 80
        btn_y = S + content_h - PAD - BTN_H
        self._draw_orange_btn(hdc, btn_x, btn_y, 80, "我知道了", self.btn_action_rect)
        self._draw_ghost_btn(
            hdc, btn_x - BTN_GAP - 80, btn_y, 80, "收起", self.btn_detail_rect
        )

    def destroy(self):
        """Force destroy this toast window."""
        if self.hwnd and not self._closed:
            user32.DestroyWindow(self.hwnd)


def _global_wnd_proc(hwnd, msg, wparam, lparam):
    """Global WNDPROC that dispatches to the correct ToastWindow."""
    tw = _hwnd_map.get(hwnd)
    if tw:
        return tw.wnd_proc(hwnd, msg, wparam, lparam)
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


# ── ToastManager ─────────────────────────────────────────────────────────────
class ToastManager:
    """Manages multiple concurrent toast windows."""

    def __init__(self, max_toasts=3):
        self.max_toasts = max_toasts
        self._toasts: dict[str, ToastWindow] = {}
        self._lock = threading.Lock()
        self._idle_event = threading.Event()
        self._idle_timeout = 60  # seconds

    def show(self, params: dict) -> bool:
        """Show a toast. Returns True on success."""
        toast_id = params.get("id", "")
        with self._lock:
            if len(self._toasts) >= self.max_toasts:
                self._dismiss_oldest()

            # Calculate y offset
            y_offset = len(self._toasts) * (COMPACT_H + SHADOW_EXTEND * 2 + 8)
            params["y_offset"] = y_offset

            tw = ToastWindow(params, on_destroyed=self._on_toast_destroyed)
            self._toasts[toast_id] = tw
            self._idle_event.clear()

        # Create toast in a new thread
        threading.Thread(target=tw.create, daemon=True).start()
        return True

    def dismiss(self, toast_id: str) -> bool:
        """Dismiss a specific toast."""
        with self._lock:
            tw = self._toasts.get(toast_id)
            if tw:
                tw.destroy()
                return True
        return False

    def _dismiss_oldest(self):
        """Dismiss the oldest toast to make room."""
        if not self._toasts:
            return
        oldest_id = next(iter(self._toasts))
        tw = self._toasts.get(oldest_id)
        if tw:
            tw.destroy()

    def _on_toast_destroyed(self, toast_id: str):
        """Called when a toast window is destroyed."""
        with self._lock:
            self._toasts.pop(toast_id, None)
            if not self._toasts:
                self._idle_event.set()

    def get_count(self) -> int:
        with self._lock:
            return len(self._toasts)

    def shutdown(self):
        """Destroy all toasts and signal idle."""
        with self._lock:
            for tw in list(self._toasts.values()):
                tw.destroy()
            self._toasts.clear()
            self._idle_event.set()

    def wait_for_idle(self, timeout=None):
        """Wait until all toasts are dismissed."""
        return self._idle_event.wait(timeout or self._idle_timeout)


# ── PipeServer ───────────────────────────────────────────────────────────────
class PipeServer:
    """Named pipe server for receiving toast requests."""

    def __init__(self, toast_manager: ToastManager):
        self.manager = toast_manager
        self._running = True

    def run(self):
        """Main loop: listen for pipe connections and handle requests."""
        logger.info("Toast daemon starting, pipe: %s", PIPE_NAME)

        while self._running:
            pipe = kernel32.CreateNamedPipeW(
                PIPE_NAME,
                PIPE_ACCESS_DUPLEX,
                PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
                PIPE_MAX_INSTANCES,
                PIPE_BUFFER_SIZE,
                PIPE_BUFFER_SIZE,
                0,
                None,
            )

            if pipe == INVALID_HANDLE_VALUE:
                logger.error("CreateNamedPipeW failed")
                time.sleep(1)
                continue

            # Wait for a client to connect
            connected = kernel32.ConnectNamedPipe(pipe, None)
            if not connected:
                err = kernel32.GetLastError()
                if err != 535:  # ERROR_PIPE_CONNECTED
                    kernel32.CloseHandle(pipe)
                    continue

            # Handle the request
            try:
                self._handle_client(pipe)
            except Exception as e:
                logger.error("Error handling client: %s", e)
            finally:
                kernel32.DisconnectNamedPipe(pipe)
                kernel32.CloseHandle(pipe)

    def _handle_client(self, pipe):
        """Read a request, dispatch, write response."""
        # Read data
        data = self._read_pipe(pipe)
        if not data:
            return

        # Parse and dispatch
        try:
            request = json.loads(data)
            response = self._dispatch(request)
        except json.JSONDecodeError as e:
            response = {"ok": False, "error": f"Invalid JSON: {e}"}
        except Exception as e:
            response = {"ok": False, "error": str(e)}

        # Write response
        response_data = json.dumps(response).encode("utf-8")
        self._write_pipe(pipe, response_data)

    def _read_pipe(self, pipe) -> bytes:
        """Read all available data from the pipe."""
        chunks = []
        buffer = ctypes.create_string_buffer(PIPE_BUFFER_SIZE)
        bytes_read = ctypes.wintypes.DWORD(0)

        while True:
            ok = kernel32.ReadFile(
                pipe,
                buffer,
                PIPE_BUFFER_SIZE - 1,
                ctypes.byref(bytes_read),
                None,
            )
            if not ok:
                err = kernel32.GetLastError()
                if err == ERROR_MORE_DATA:
                    chunks.append(buffer.raw[: bytes_read.value])
                    continue
                elif err == ERROR_BROKEN_PIPE:
                    break
                else:
                    break
            else:
                chunks.append(buffer.raw[: bytes_read.value])
                break

        return b"".join(chunks)

    def _write_pipe(self, pipe, data: bytes):
        """Write data to the pipe."""
        bytes_written = ctypes.wintypes.DWORD(0)
        kernel32.WriteFile(pipe, data, len(data), ctypes.byref(bytes_written), None)

    def _dispatch(self, request: dict) -> dict:
        """Dispatch a request to the appropriate handler."""
        cmd = request.get("cmd", "")

        if cmd == "show":
            return self._handle_show(request)
        elif cmd == "dismiss":
            return self._handle_dismiss(request)
        elif cmd == "ping":
            return {"ok": True, "pong": True}
        elif cmd == "quit":
            self._running = False
            self.manager.shutdown()
            return {"ok": True}
        else:
            return {"ok": False, "error": f"Unknown command: {cmd}"}

    def _handle_show(self, params: dict) -> dict:
        """Handle a show toast request."""
        toast_id = params.get("id", "")
        if not toast_id:
            return {"ok": False, "error": "Missing id"}

        success = self.manager.show(params)
        if success:
            return {"ok": True, "id": toast_id}
        else:
            return {"ok": False, "error": "max_toasts_reached"}

    def _handle_dismiss(self, request: dict) -> dict:
        """Handle a dismiss toast request."""
        toast_id = request.get("id", "")
        if not toast_id:
            return {"ok": False, "error": "Missing id"}

        success = self.manager.dismiss(toast_id)
        return {"ok": success}


# ── Entry point ──────────────────────────────────────────────────────────────
def run_toast_daemon():
    """Run the toast daemon process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    manager = ToastManager()
    server = PipeServer(manager)

    # Start idle timeout thread
    def _idle_watch():
        while server._running:
            if manager.wait_for_idle():
                # All toasts dismissed, wait a bit more for new requests
                time.sleep(2)
                if manager.get_count() == 0 and server._running:
                    logger.info("Idle timeout, exiting")
                    server._running = False
                    # Connect to self to unblock the pipe listen
                    try:
                        h = kernel32.CreateFileW(
                            PIPE_NAME,
                            0x80000000 | 0x40000000,
                            0,
                            None,
                            3,
                            0,
                            None,
                        )
                        if h != INVALID_HANDLE_VALUE:
                            kernel32.CloseHandle(h)
                    except Exception:
                        pass

    threading.Thread(target=_idle_watch, daemon=True).start()

    # Run the pipe server
    server.run()
    logger.info("Toast daemon exiting")


if __name__ == "__main__":
    run_toast_daemon()
