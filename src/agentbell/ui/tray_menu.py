"""Productized dark tray panel for AgentBell.

Replaces system default popup with Claude/Anthropic styled panel:
- Brand header with orange >_ icon + status dot
- Menu items with hover states and badges
- Large rounded corners, dark gradient background
"""

import ctypes
import ctypes.wintypes
import sys
import time

from agentbell.ui.theme import (
    BG_BGR, DARK_BGR, BG_ELEVATED_BGR, LIGHT_BGR, MID_GRAY_BGR,
    ORANGE_BGR, GREEN_BGR, BG_HOVER_BGR, BG_ACTIVE_BGR,
    BORDER_BGR, SEPARATOR_BGR, TEXT_MUTED_BGR,
    TRAY_MENU_W, TRAY_MENU_MIN_H, RADIUS_WINDOW,
    HEADER_H_PANEL, ITEM_H_PANEL, PADDING_PANEL,
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


# Menu items definition
_ITEMS = [
    {"id": ID_RECENT, "icon_clipboard": True, "label": "最近事件", "badge": True},
    {"id": ID_MUTE, "icon_mute": True, "label": "静音 30 分钟", "toggle": True},
    None,  # separator
    {"id": ID_SETTINGS, "icon_gear": True, "label": "设置", "disabled": True},
    {"id": ID_ABOUT, "icon_info": True, "label": "关于 AgentBell"},
    None,  # separator
    {"id": ID_QUIT, "icon_power": True, "label": "退出 AgentBell"},
]

SEPARATOR_H = 8


def _draw_icon_clipboard(hdc, x, y, size, color):
    """Draw clipboard icon (two overlapping rectangles)."""
    pen = gdi32.CreatePen(1, 1, color)
    old_p = gdi32.SelectObject(hdc, pen)
    old_b = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
    # Back rectangle
    gdi32.RoundRect(hdc, x + 2, y + 2, x + size - 2, y + size - 2, 2, 2)
    # Front rectangle (offset)
    gdi32.RoundRect(hdc, x, y, x + size - 4, y + size - 4, 2, 2)
    gdi32.SelectObject(hdc, old_p)
    gdi32.SelectObject(hdc, old_b)
    gdi32.DeleteObject(pen)


def _draw_icon_mute(hdc, x, y, size, color):
    """Draw mute bell icon (bell + diagonal slash)."""
    pen = gdi32.CreatePen(1, 1, color)
    old_p = gdi32.SelectObject(hdc, pen)
    old_b = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
    # Bell body (simplified as arc)
    cx, cy = x + size // 2, y + size // 2
    r = size // 3
    gdi32.Arc(hdc, cx - r, cy - r, cx + r, cy + r - 2, cx + r, cy - r, cx - r, cy - r)
    # Clapper
    gdi32.MoveToEx(hdc, cx - 2, cy + r - 2, None)
    gdi32.LineTo(hdc, cx + 2, cy + r - 2)
    # Diagonal slash
    gdi32.MoveToEx(hdc, x + 2, y + size - 2, None)
    gdi32.LineTo(hdc, x + size - 2, y + 2)
    gdi32.SelectObject(hdc, old_p)
    gdi32.SelectObject(hdc, old_b)
    gdi32.DeleteObject(pen)


def _draw_icon_gear(hdc, x, y, size, color):
    """Draw gear icon (simplified as circle with teeth)."""
    pen = gdi32.CreatePen(1, 1, color)
    old_p = gdi32.SelectObject(hdc, pen)
    old_b = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
    cx, cy = x + size // 2, y + size // 2
    r = size // 3
    gdi32.Ellipse(hdc, cx - r, cy - r, cx + r, cy + r)
    # Teeth (simplified as lines)
    for angle in [0, 60, 120, 180, 240, 300]:
        import math
        rad = math.radians(angle)
        x1 = cx + int((r + 2) * math.cos(rad))
        y1 = cy + int((r + 2) * math.sin(rad))
        x2 = cx + int((r + 5) * math.cos(rad))
        y2 = cy + int((r + 5) * math.sin(rad))
        gdi32.MoveToEx(hdc, x1, y1, None)
        gdi32.LineTo(hdc, x2, y2)
    gdi32.SelectObject(hdc, old_p)
    gdi32.SelectObject(hdc, old_b)
    gdi32.DeleteObject(pen)


def _draw_icon_info(hdc, x, y, size, color):
    """Draw question mark in circle."""
    pen = gdi32.CreatePen(1, 1, color)
    old_p = gdi32.SelectObject(hdc, pen)
    old_b = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
    cx, cy = x + size // 2, y + size // 2
    r = size // 2 - 1
    gdi32.Ellipse(hdc, cx - r, cy - r, cx + r, cy + r)
    gdi32.SelectObject(hdc, old_p)
    gdi32.SelectObject(hdc, old_b)
    gdi32.DeleteObject(pen)
    # "?" text
    gdi32.SetBkMode(hdc, TRANSPARENT)
    gdi32.SetTextColor(hdc, color)
    f = gdi32.CreateFontW(-12, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
    old_f = gdi32.SelectObject(hdc, f)
    rct = _RECT(x, y, x + size, y + size)
    user32.DrawTextW(hdc, "?", -1, ctypes.byref(rct), 0x0001 | 0x0004)
    gdi32.SelectObject(hdc, old_f)
    gdi32.DeleteObject(f)


def _draw_icon_power(hdc, x, y, size, color):
    """Draw power icon (circle with vertical line)."""
    pen = gdi32.CreatePen(2, 1, color)
    old_p = gdi32.SelectObject(hdc, pen)
    old_b = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
    cx, cy = x + size // 2, y + size // 2
    r = size // 3
    # Arc (top part of circle)
    gdi32.Arc(hdc, cx - r, cy - r, cx + r, cy + r, cx, cy - r - 1, cx, cy - r - 1)
    # Vertical line
    gdi32.MoveToEx(hdc, cx, cy - r - 2, None)
    gdi32.LineTo(hdc, cx, cy - 1)
    gdi32.SelectObject(hdc, old_p)
    gdi32.SelectObject(hdc, old_b)
    gdi32.DeleteObject(pen)


class TrayMenu:
    """Productized dark tray panel with brand header and menu items."""

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
        h = HEADER_H_PANEL + PADDING_PANEL
        for item in _ITEMS:
            if item is None:
                h += SEPARATOR_H
            else:
                h += ITEM_H_PANEL
        return h + PADDING_PANEL

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
        # Apply rounded corner region
        rgn = gdi32.CreateRoundRectRgn(0, 0, TRAY_MENU_W + 1, h + 1,
                                        RADIUS_WINDOW * 2, RADIUS_WINDOW * 2)
        user32.SetWindowRgn(self._hwnd, rgn, True)

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

    def _draw_item_icon(self, hdc, item, x, y, size, color):
        """Draw the appropriate icon for a menu item."""
        if item.get("icon_clipboard"):
            _draw_icon_clipboard(hdc, x, y, size, color)
        elif item.get("icon_mute"):
            _draw_icon_mute(hdc, x, y, size, color)
        elif item.get("icon_gear"):
            _draw_icon_gear(hdc, x, y, size, color)
        elif item.get("icon_info"):
            _draw_icon_info(hdc, x, y, size, color)
        elif item.get("icon_power"):
            _draw_icon_power(hdc, x, y, size, color)

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

        # ── Brand Header ──────────────────────────────────────────────────────
        # Orange >_ icon (28x28) + title + status dot
        icon_x = PADDING_PANEL
        icon_y = PADDING_PANEL + 6
        icon_size = 28
        icon_r = 8

        # Draw orange rounded square
        icon_brush = gdi32.CreateSolidBrush(ORANGE_BGR)
        old_ib = gdi32.SelectObject(hdc, icon_brush)
        old_ip = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
        gdi32.RoundRect(hdc, icon_x, icon_y, icon_x + icon_size, icon_y + icon_size, icon_r, icon_r)
        gdi32.SelectObject(hdc, old_ib)
        gdi32.SelectObject(hdc, old_ip)
        gdi32.DeleteObject(icon_brush)

        # Draw white >_ text centered in icon
        gdi32.SetBkMode(hdc, TRANSPARENT)
        gdi32.SetTextColor(hdc, 0x00FFFFFF)  # white
        icon_font = gdi32.CreateFontW(-13, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 0, 0, 'Consolas')
        old_if = gdi32.SelectObject(hdc, icon_font)
        icon_rect = _RECT(icon_x, icon_y, icon_x + icon_size, icon_y + icon_size)
        user32.DrawTextW(hdc, ">_", -1, ctypes.byref(icon_rect), 0x0001 | 0x0004)
        gdi32.SelectObject(hdc, old_if)
        gdi32.DeleteObject(icon_font)

        # Title text
        gdi32.SetTextColor(hdc, LIGHT_BGR)
        header_font = gdi32.CreateFontW(-14, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, header_font)
        hr = _RECT(PADDING_PANEL + icon_size + 10, PADDING_PANEL + 8, w - PADDING_PANEL, PADDING_PANEL + 28)
        user32.DrawTextW(hdc, "AgentBell", -1, ctypes.byref(hr), 0)

        # Status dot + label
        is_muted = self.daemon.is_muted()
        dot_color = GREEN_BGR if not is_muted else MID_GRAY_BGR
        dot_brush = gdi32.CreateSolidBrush(dot_color)
        old_b = gdi32.SelectObject(hdc, dot_brush)
        old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
        dot_x = PADDING_PANEL + icon_size + 10
        dot_y = PADDING_PANEL + 34
        gdi32.Ellipse(hdc, dot_x, dot_y, dot_x + 7, dot_y + 7)
        gdi32.SelectObject(hdc, old_b)
        gdi32.SelectObject(hdc, old_p)
        gdi32.DeleteObject(dot_brush)

        gdi32.SetTextColor(hdc, MID_GRAY_BGR)
        status_font = gdi32.CreateFontW(-11, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f2 = gdi32.SelectObject(hdc, status_font)
        sr = _RECT(dot_x + 12, dot_y - 2, w - PADDING_PANEL, dot_y + 16)
        if is_muted:
            remaining = int((self.daemon._muted_until - time.time()) / 60)
            status_text = f"已静音 · 剩余 {remaining} 分钟" if remaining > 0 else "已静音"
        else:
            status_text = "运行中"
        user32.DrawTextW(hdc, status_text, -1, ctypes.byref(sr), 0)
        gdi32.SelectObject(hdc, old_f2)
        gdi32.DeleteObject(status_font)
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(header_font)

        # ── Header separator ──────────────────────────────────────────────────
        sep_brush = gdi32.CreateSolidBrush(SEPARATOR_BGR)
        sep_rect = _RECT(PADDING_PANEL, HEADER_H_PANEL, w - PADDING_PANEL, HEADER_H_PANEL + 1)
        user32.FillRect(hdc, ctypes.byref(sep_rect), sep_brush)
        gdi32.DeleteObject(sep_brush)

        # ── Menu Items ────────────────────────────────────────────────────────
        self._item_rects = []
        y = HEADER_H_PANEL + PADDING_PANEL

        badge_count = self.daemon.event_store.get_pending_permission_count()

        for item in _ITEMS:
            if item is None:
                # Separator
                sep_brush = gdi32.CreateSolidBrush(SEPARATOR_BGR)
                sep_rect = _RECT(PADDING_PANEL, y + 3, w - PADDING_PANEL, y + 4)
                user32.FillRect(hdc, ctypes.byref(sep_rect), sep_brush)
                gdi32.DeleteObject(sep_brush)
                y += SEPARATOR_H
                continue

            item_id = item["id"]
            is_hover = len(self._item_rects) == self._hover_idx
            is_disabled = item.get("disabled", False)

            # Hover background (orange tint)
            if is_hover and not is_disabled:
                hover_brush = gdi32.CreateSolidBrush(BG_HOVER_BGR)
                hover_rect = _RECT(PADDING_PANEL, y, w - PADDING_PANEL, y + ITEM_H_PANEL)
                user32.FillRect(hdc, ctypes.byref(hover_rect), hover_brush)
                gdi32.DeleteObject(hover_brush)

            # Icon (GDI drawn, not emoji)
            icon_x = PADDING_PANEL + 8
            icon_y_item = y + (ITEM_H_PANEL - 20) // 2
            icon_color = ORANGE_BGR if is_hover else (MID_GRAY_BGR if not is_disabled else 0x00505050)
            self._draw_item_icon(hdc, item, icon_x, icon_y_item, 20, icon_color)

            # Label
            label = item["label"]
            if item.get("toggle") and self.daemon.is_muted():
                remaining = int((self.daemon._muted_until - time.time()) / 60)
                if remaining > 0:
                    label = f"已静音 · 剩余 {remaining} 分钟"
                else:
                    label = "取消静音"

            label_color = LIGHT_BGR if not is_disabled else 0x00606060
            if is_hover and not is_disabled:
                label_color = ORANGE_BGR
            gdi32.SetTextColor(hdc, label_color)
            label_font = gdi32.CreateFontW(-13, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
            old_f2 = gdi32.SelectObject(hdc, label_font)
            lr = _RECT(PADDING_PANEL + 36, y, w - PADDING_PANEL - 10, y + ITEM_H_PANEL)
            user32.DrawTextW(hdc, label, -1, ctypes.byref(lr), 0x0004)  # DT_VCENTER
            gdi32.SelectObject(hdc, old_f2)
            gdi32.DeleteObject(label_font)

            # Badge (orange dot with count)
            if item.get("badge") and badge_count > 0:
                badge_text = str(badge_count) if badge_count <= 9 else "9+"
                badge_dot_size = 16
                badge_x = w - PADDING_PANEL - 24
                badge_y = y + (ITEM_H_PANEL - badge_dot_size) // 2
                # Orange badge background
                badge_brush = gdi32.CreateSolidBrush(ORANGE_BGR)
                old_bb = gdi32.SelectObject(hdc, badge_brush)
                old_bp = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
                gdi32.Ellipse(hdc, badge_x, badge_y, badge_x + badge_dot_size, badge_y + badge_dot_size)
                gdi32.SelectObject(hdc, old_bb)
                gdi32.SelectObject(hdc, old_bp)
                gdi32.DeleteObject(badge_brush)
                # Badge number
                gdi32.SetTextColor(hdc, 0x00FFFFFF)
                badge_font = gdi32.CreateFontW(-9, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
                old_f3 = gdi32.SelectObject(hdc, badge_font)
                br = _RECT(badge_x, badge_y, badge_x + badge_dot_size, badge_y + badge_dot_size)
                user32.DrawTextW(hdc, badge_text, -1, ctypes.byref(br), 0x0001 | 0x0004)
                gdi32.SelectObject(hdc, old_f3)
                gdi32.DeleteObject(badge_font)

            self._item_rects.append((y, y + ITEM_H_PANEL, item_id))
            y += ITEM_H_PANEL

        user32.EndPaint(hwnd, ctypes.byref(ps))
