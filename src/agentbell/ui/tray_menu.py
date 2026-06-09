"""Custom dark-themed tray context menu.

Replaces system default popup menu with Claude/Anthropic styled popup.
"""

import ctypes
import ctypes.wintypes
import sys
import time

from agentbell.ui.theme import (
    BG_BGR, DARK_BGR, BG_ELEVATED_BGR, LIGHT_BGR, MID_GRAY_BGR,
    ORANGE_BGR, GREEN_BGR, BG_HOVER_BGR, BG_ACTIVE_BGR,
    TRAY_MENU_W, TRAY_MENU_MIN_H, RADIUS_WINDOW,
    FONT_FAMILY,
)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

LRESULT = ctypes.c_longlong if sys.maxsize > 2**32 else ctypes.c_long
LP = ctypes.c_longlong if sys.maxsize > 2**32 else ctypes.c_long
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, LP)
NULL_PEN = 8
TRANSPARENT = 1

# Menu item IDs
ID_RECENT = 1001
ID_MUTE = 1002
ID_SETTINGS = 1003
ID_ABOUT = 1004
ID_QUIT = 1005


class _PS(ctypes.Structure):
    _fields_ = [('hdc', ctypes.wintypes.HDC), ('fErase', ctypes.wintypes.BOOL),
                ('rc', ctypes.wintypes.RECT), ('fR', ctypes.wintypes.BOOL),
                ('fI', ctypes.wintypes.BOOL), ('r', ctypes.c_byte * 32)]


class _RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


# Menu item definition
_ITEMS = [
    {"id": ID_RECENT, "icon": "📋", "label": "最近事件", "badge": True},
    {"id": ID_MUTE, "icon": "🔇", "label": "静音 30 分钟", "toggle": True},
    None,  # separator
    {"id": ID_SETTINGS, "icon": "⚙", "label": "设置", "disabled": True},
    {"id": ID_ABOUT, "icon": "ℹ", "label": "关于 AgentBell"},
    None,  # separator
    {"id": ID_QUIT, "icon": "⏻", "label": "退出 AgentBell"},
]

ITEM_H = 42
SEPARATOR_H = 8
HEADER_H = 48
PADDING = 10


class TrayMenu:
    """Custom dark-themed tray context menu."""

    def __init__(self, daemon, on_action=None):
        self.daemon = daemon
        self.on_action = on_action  # callback(id)
        self._hwnd = None
        self._visible = False
        self._hover_idx = -1
        self._item_rects = []  # [(top, bottom, id), ...]
        self._wnd_proc_ref = None
        self._class_name = "AgentBellTrayMenu"

    def _ensure_class(self):
        user32.DefWindowProcW.argtypes = [ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, LP]
        user32.DefWindowProcW.restype = LRESULT

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == 0x000F:  # WM_PAINT
                self._paint(hwnd)
                return 0
            elif msg == 0x0014:  # WM_ERASEBKGND
                return 1
            elif msg == 0x0201:  # WM_LBUTTONDOWN
                x = lparam & 0xFFFF
                y = (lparam >> 16) & 0xFFFF
                self._handle_click(x, y)
                return 0
            elif msg == 0x0200:  # WM_MOUSEMOVE
                x = lparam & 0xFFFF
                y = (lparam >> 16) & 0xFFFF
                old = self._hover_idx
                self._hover_idx = -1
                for i, (top, bottom, item_id) in enumerate(self._item_rects):
                    if top <= y <= bottom:
                        self._hover_idx = i
                        break
                if self._hover_idx != old:
                    user32.InvalidateRect(hwnd, None, True)
                IDC_ARROW = 32512
                IDC_HAND = 32649
                user32.SetCursor(user32.LoadCursorW(0, IDC_HAND if self._hover_idx >= 0 else IDC_ARROW))
                return 0
            elif msg == 0x0020:  # WM_SETCURSOR
                user32.SetCursor(user32.LoadCursorW(0, 32512))
                return 1
            elif msg == 0x0008:  # WM_KILLFOCUS
                self.hide()
                return 0
            elif msg == 0x001C:  # WM_ACTIVATEAPP
                if wparam == 0:
                    self.hide()
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wnd_proc_ref = WNDPROC(wnd_proc)

        class WNDCLASS(ctypes.Structure):
            _fields_ = [('style', ctypes.c_uint), ('lpfnWndProc', WNDPROC),
                        ('cbClsExtra', ctypes.c_int), ('cbWndExtra', ctypes.c_int),
                        ('hInstance', ctypes.wintypes.HINSTANCE), ('hIcon', ctypes.wintypes.HICON),
                        ('hCursor', ctypes.wintypes.HANDLE), ('hbrBackground', ctypes.wintypes.HANDLE),
                        ('lpszMenuName', ctypes.wintypes.LPCWSTR), ('lpszClassName', ctypes.wintypes.LPCWSTR)]

        wc = WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc_ref
        wc.lpszClassName = self._class_name
        wc.hbrBackground = gdi32.CreateSolidBrush(BG_BGR)
        wc.cr = user32.LoadCursorW(0, 32512)
        user32.RegisterClassW(ctypes.byref(wc))

    def _calc_height(self):
        h = HEADER_H + PADDING
        for item in _ITEMS:
            if item is None:
                h += SEPARATOR_H
            else:
                h += ITEM_H
        return h + PADDING

    def _create_window(self):
        if self._hwnd:
            return
        self._ensure_class()
        h = self._calc_height()
        ex = 0x00000008 | 0x00000080 | 0x08000000  # TOPMOST | TOOLWINDOW | NOACTIVATE
        self._hwnd = user32.CreateWindowExW(
            ex, self._class_name, 'AgentBell', 0x80000000,
            0, 0, TRAY_MENU_W, h, 0, 0, 0, None,
        )

    def show(self):
        """Show menu near cursor."""
        self._create_window()
        h = self._calc_height()

        point = ctypes.wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))

        # Position above cursor, aligned right
        x = point.x - TRAY_MENU_W
        y = point.y - h - 4
        if y < 0:
            y = point.y + 4

        user32.MoveWindow(self._hwnd, x, y, TRAY_MENU_W, h, True)
        user32.ShowWindow(self._hwnd, 5)  # SW_SHOWNOACTIVATE
        user32.SetWindowPos(self._hwnd, -1, x, y, TRAY_MENU_W, h, 0x0010 | 0x0040)
        user32.InvalidateRect(self._hwnd, None, True)
        user32.UpdateWindow(self._hwnd)
        self._visible = True

    def hide(self):
        if self._hwnd:
            user32.ShowWindow(self._hwnd, 0)
            self._visible = False

    def toggle(self):
        if self._visible:
            self.hide()
        else:
            self.show()

    def _handle_click(self, x, y):
        for top, bottom, item_id in self._item_rects:
            if top <= y <= bottom:
                # Check if item is disabled
                for item in _ITEMS:
                    if item and item["id"] == item_id and item.get("disabled"):
                        return
                self.hide()
                if self.on_action:
                    self.on_action(item_id)
                return
        # Click outside items - close
        self.hide()

    def _paint(self, hwnd):
        ps = _PS()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
        rc = _RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rc))
        w, h = rc.right, rc.bottom

        # Background
        brush = gdi32.CreateSolidBrush(BG_BGR)
        user32.FillRect(hdc, ctypes.byref(rc), brush)
        gdi32.DeleteObject(brush)

        # Header
        gdi32.SetBkMode(hdc, TRANSPARENT)
        gdi32.SetTextColor(hdc, LIGHT_BGR)
        header_font = gdi32.CreateFontW(-14, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, header_font)
        hr = _RECT(PADDING, PADDING, w - PADDING, PADDING + 20)
        user32.DrawTextW(hdc, "AgentBell", -1, ctypes.byref(hr), 0)  # DT_LEFT

        # Status dot + label
        dot_brush = gdi32.CreateSolidBrush(GREEN_BGR)
        old_b = gdi32.SelectObject(hdc, dot_brush)
        old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
        gdi32.Ellipse(hdc, PADDING, PADDING + 24, PADDING + 7, PADDING + 31)
        gdi32.SelectObject(hdc, old_b)
        gdi32.SelectObject(hdc, old_p)
        gdi32.DeleteObject(dot_brush)

        gdi32.SetTextColor(hdc, MID_GRAY_BGR)
        status_font = gdi32.CreateFontW(-11, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f2 = gdi32.SelectObject(hdc, status_font)
        sr = _RECT(PADDING + 12, PADDING + 22, w - PADDING, PADDING + 36)
        user32.DrawTextW(hdc, "运行中", -1, ctypes.byref(sr), 0)
        gdi32.SelectObject(hdc, old_f2)
        gdi32.DeleteObject(status_font)
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(header_font)

        # Separator after header
        sep_brush = gdi32.CreateSolidBrush(0x001A1918)
        sep_rect = _RECT(PADDING, HEADER_H - 2, w - PADDING, HEADER_H - 1)
        user32.FillRect(hdc, ctypes.byref(sep_rect), sep_brush)
        gdi32.DeleteObject(sep_brush)

        # Menu items
        self._item_rects = []
        y = HEADER_H + PADDING

        badge_count = self.daemon.registry.get_pending_permission_count()

        for item in _ITEMS:
            if item is None:
                # Separator
                sep_brush = gdi32.CreateSolidBrush(0x001A1918)
                sep_rect = _RECT(PADDING, y + 3, w - PADDING, y + 4)
                user32.FillRect(hdc, ctypes.byref(sep_rect), sep_brush)
                gdi32.DeleteObject(sep_brush)
                y += SEPARATOR_H
                continue

            item_id = item["id"]
            is_hover = len(self._item_rects) == self._hover_idx
            is_disabled = item.get("disabled", False)

            # Hover background
            if is_hover and not is_disabled:
                hover_brush = gdi32.CreateSolidBrush(BG_HOVER_BGR)
                hover_rect = _RECT(PADDING, y, w - PADDING, y + ITEM_H)
                user32.FillRect(hdc, ctypes.byref(hover_rect), hover_brush)
                gdi32.DeleteObject(hover_brush)

            # Icon (text symbol)
            icon_x = PADDING + 4
            icon_color = MID_GRAY_BGR if not is_disabled else 0x00505050
            gdi32.SetTextColor(hdc, icon_color)
            icon_font = gdi32.CreateFontW(-14, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
            old_f = gdi32.SelectObject(hdc, icon_font)
            ir = _RECT(icon_x, y, icon_x + 20, y + ITEM_H)
            user32.DrawTextW(hdc, item["icon"], -1, ctypes.byref(ir), 0x0001 | 0x0004)

            # Label
            label = item["label"]
            if item.get("toggle") and self.daemon.is_muted():
                remaining = int((self.daemon._muted_until - time.time()) / 60)
                if remaining > 0:
                    label = f"已静音 · 剩余 {remaining} 分钟"
                else:
                    label = "取消静音"

            label_color = LIGHT_BGR if not is_disabled else 0x00606060
            gdi32.SetTextColor(hdc, label_color)
            label_font = gdi32.CreateFontW(-13, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
            old_f2 = gdi32.SelectObject(hdc, label_font)
            lr = _RECT(PADDING + 30, y, w - PADDING - 10, y + ITEM_H)
            user32.DrawTextW(hdc, label, -1, ctypes.byref(lr), 0x0004)  # DT_VCENTER

            # Badge for recent events
            if item.get("badge") and badge_count > 0:
                badge_text = str(badge_count) if badge_count <= 9 else "9+"
                gdi32.SetTextColor(hdc, ORANGE_BGR)
                badge_font = gdi32.CreateFontW(-11, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
                old_f3 = gdi32.SelectObject(hdc, badge_font)
                br = _RECT(w - PADDING - 30, y, w - PADDING - 10, y + ITEM_H)
                user32.DrawTextW(hdc, badge_text, -1, ctypes.byref(br), 0x0002 | 0x0004)  # DT_RIGHT | DT_VCENTER
                gdi32.SelectObject(hdc, old_f3)
                gdi32.DeleteObject(badge_font)

            gdi32.SelectObject(hdc, old_f)
            gdi32.DeleteObject(icon_font)
            gdi32.SelectObject(hdc, old_f2)
            gdi32.DeleteObject(label_font)

            self._item_rects.append((y, y + ITEM_H, item_id))
            y += ITEM_H

        user32.EndPaint(hwnd, ctypes.byref(ps))
