"""Custom dark-themed Recent Events window.

Replaces QMessageBox with a Claude/Anthropic styled window.
Shows event cards with status dots, session labels, timestamps.
"""

import ctypes
import ctypes.wintypes
import sys
import time

from agentbell.ui.theme import (
    BG_BGR, DARK_BGR, BG_ELEVATED_BGR, LIGHT_BGR, MID_GRAY_BGR,
    ORANGE_BGR, GREEN_BGR, BLUE_BGR, RED_BGR,
    BG_CARD_BGR, BG_CARD_HOVER_BGR, BG_HOVER_BGR,
    RADIUS_WINDOW, RADIUS_CARD, RADIUS_BUTTON,
    RECENT_EVENTS_W, RECENT_EVENTS_H,
    STATE_LABELS, STATUS_BGR,
    FONT_FAMILY,
)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

LRESULT = ctypes.c_longlong if sys.maxsize > 2**32 else ctypes.c_long
LP = ctypes.c_longlong if sys.maxsize > 2**32 else ctypes.c_long
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, LP)
NULL_PEN = 8
TRANSPARENT = 1
DT_LEFT = 0
DT_RIGHT = 2
DT_VCENTER = 4
DT_SINGLELINE = 0x20


class _PS(ctypes.Structure):
    _fields_ = [('hdc', ctypes.wintypes.HDC), ('fErase', ctypes.wintypes.BOOL),
                ('rc', ctypes.wintypes.RECT), ('fR', ctypes.wintypes.BOOL),
                ('fI', ctypes.wintypes.BOOL), ('r', ctypes.c_byte * 32)]


class _RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class RecentEventsWindow:
    """Custom dark-themed recent events window."""

    def __init__(self, daemon):
        self.daemon = daemon
        self._hwnd = None
        self._visible = False
        self._wnd_proc_ref = None
        self._close_rect = [0, 0, 0, 0]
        self._card_rects = []  # [(y_top, y_bottom, session_id), ...]
        self._class_name = "AgentBellRecentEvents"

    def _ensure_class(self):
        """Register window class."""
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
                if self._hit_test(x, y, self._close_rect):
                    self.hide()
                    return 0
                # Check card clicks
                for card_top, card_bottom, session_id in self._card_rects:
                    if card_top <= y <= card_bottom:
                        # Could expand detail or copy session info
                        pass
                return 0
            elif msg == 0x0200:  # WM_MOUSEMOVE
                x = lparam & 0xFFFF
                y = (lparam >> 16) & 0xFFFF
                in_btn = self._hit_test(x, y, self._close_rect)
                for ct, cb, _ in self._card_rects:
                    if ct <= y <= cb:
                        in_btn = True
                        break
                IDC_ARROW = 32512
                IDC_HAND = 32649
                user32.SetCursor(user32.LoadCursorW(0, IDC_HAND if in_btn else IDC_ARROW))
                return 0
            elif msg == 0x0020:  # WM_SETCURSOR
                user32.SetCursor(user32.LoadCursorW(0, 32512))
                return 1
            elif msg == 0x0008:  # WM_KILLFOCUS
                self.hide()
                return 0
            elif msg == 0x0002:  # WM_DESTROY
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

    def _create_window(self):
        """Create the window if not exists."""
        if self._hwnd:
            return
        self._ensure_class()

        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        x = sw - RECENT_EVENTS_W - 24
        y = sh - RECENT_EVENTS_H - 60

        ex = 0x00000008 | 0x00000080 | 0x08000000  # TOPMOST | TOOLWINDOW | NOACTIVATE
        self._hwnd = user32.CreateWindowExW(
            ex, self._class_name, 'AgentBell', 0x80000000,  # WS_POPUP
            x, y, RECENT_EVENTS_W, RECENT_EVENTS_H, 0, 0, 0, None,
        )

    def show(self):
        """Show the window."""
        self._create_window()
        sessions = self.daemon.registry.get_all()
        h = max(220, 100 + len(sessions[-20:]) * 82)

        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        x = sw - RECENT_EVENTS_W - 24
        y = sh - h - 60

        user32.MoveWindow(self._hwnd, x, y, RECENT_EVENTS_W, h, True)
        user32.ShowWindow(self._hwnd, 5)  # SW_SHOWNOACTIVATE
        user32.SetWindowPos(self._hwnd, -1, x, y, RECENT_EVENTS_W, h, 0x0010 | 0x0040)
        user32.UpdateWindow(self._hwnd)
        user32.InvalidateRect(self._hwnd, None, True)
        self._visible = True

    def hide(self):
        """Hide the window."""
        if self._hwnd:
            user32.ShowWindow(self._hwnd, 0)  # SW_HIDE
            self._visible = False

    def toggle(self):
        """Toggle visibility."""
        if self._visible:
            self.hide()
        else:
            self.show()

    @staticmethod
    def _hit_test(x, y, rect):
        return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]

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

        PAD = 16

        # Header: bell icon + title
        gdi32.SetBkMode(hdc, TRANSPARENT)
        gdi32.SetTextColor(hdc, LIGHT_BGR)
        title_font = gdi32.CreateFontW(-16, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, title_font)
        tr = _RECT(PAD, PAD, w - 30, PAD + 20)
        user32.DrawTextW(hdc, "AgentBell 最近事件", -1, ctypes.byref(tr), DT_LEFT | DT_VCENTER)
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(title_font)

        # Close button
        close_font = gdi32.CreateFontW(-16, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, close_font)
        gdi32.SetTextColor(hdc, MID_GRAY_BGR)
        cr = _RECT(w - 28, PAD - 2, w - 10, PAD + 16)
        user32.DrawTextW(hdc, "\\u00d7", -1, ctypes.byref(cr), 0x0001 | 0x0004)
        self._close_rect = [w - 28, PAD - 2, w - 10, PAD + 16]
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(close_font)

        # Subtitle
        sessions = self.daemon.registry.get_all()
        count = len(sessions)
        t = time.strftime("%H:%M")
        subtitle = f"运行中 · {count} 个事件 · {t}"
        gdi32.SetTextColor(hdc, MID_GRAY_BGR)
        sub_font = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, sub_font)
        sr = _RECT(PAD, PAD + 22, w - 30, PAD + 36)
        user32.DrawTextW(hdc, subtitle, -1, ctypes.byref(sr), DT_LEFT | DT_VCENTER)
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(sub_font)

        # Separator
        sep_brush = gdi32.CreateSolidBrush(0x001A1918)  # border color
        sep_rect = _RECT(PAD, PAD + 44, w - PAD, PAD + 45)
        user32.FillRect(hdc, ctypes.byref(sep_rect), sep_brush)
        gdi32.DeleteObject(sep_brush)

        # Event cards
        self._card_rects = []
        card_y = PAD + 52
        card_w = w - PAD * 2
        card_h = 74
        card_gap = 8

        recent = sessions[-20:]  # last 20
        if not recent:
            # Empty state
            gdi32.SetTextColor(hdc, MID_GRAY_BGR)
            empty_font = gdi32.CreateFontW(-13, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
            old_f = gdi32.SelectObject(hdc, empty_font)
            er = _RECT(PAD, card_y + 20, w - PAD, card_y + 60)
            user32.DrawTextW(hdc, "暂无最近事件", -1, ctypes.byref(er), 0x0001 | 0x0004)
            gdi32.SelectObject(hdc, old_f)
            gdi32.DeleteObject(empty_font)
        else:
            for s in reversed(recent):
                if card_y + card_h > h - PAD:
                    break

                # Card background
                card_brush = gdi32.CreateSolidBrush(BG_CARD_BGR)
                old_b = gdi32.SelectObject(hdc, card_brush)
                old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
                gdi32.RoundRect(hdc, PAD, card_y, PAD + card_w, card_y + card_h, RADIUS_CARD, RADIUS_CARD)
                gdi32.SelectObject(hdc, old_b)
                gdi32.SelectObject(hdc, old_p)
                gdi32.DeleteObject(card_brush)

                # Status dot
                dot_color = STATUS_BGR.get(s.state, MID_GRAY_BGR)
                dot_brush = gdi32.CreateSolidBrush(dot_color)
                old_b = gdi32.SelectObject(hdc, dot_brush)
                old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
                gdi32.Ellipse(hdc, PAD + 12, card_y + 12, PAD + 19, card_y + 19)
                gdi32.SelectObject(hdc, old_b)
                gdi32.SelectObject(hdc, old_p)
                gdi32.DeleteObject(dot_brush)

                # Status label + timestamp
                state_label = STATE_LABELS.get(s.state, s.state)
                gdi32.SetTextColor(hdc, LIGHT_BGR)
                label_font = gdi32.CreateFontW(-12, 0, 0, 0, 500, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
                old_f = gdi32.SelectObject(hdc, label_font)
                lr = _RECT(PAD + 24, card_y + 10, PAD + card_w - 60, card_y + 24)
                user32.DrawTextW(hdc, state_label, -1, ctypes.byref(lr), DT_LEFT | DT_VCENTER)

                # Timestamp
                ts = time.strftime("%H:%M:%S", time.localtime(s.last_event_time))
                gdi32.SetTextColor(hdc, MID_GRAY_BGR)
                ts_rect = _RECT(PAD + card_w - 60, card_y + 10, PAD + card_w - 10, card_y + 24)
                user32.DrawTextW(hdc, ts, -1, ctypes.byref(ts_rect), DT_RIGHT | DT_VCENTER)
                gdi32.SelectObject(hdc, old_f)
                gdi32.DeleteObject(label_font)

                # Session label + event type
                gdi32.SetTextColor(hdc, MID_GRAY_BGR)
                info_font = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
                old_f = gdi32.SelectObject(hdc, info_font)
                info_text = f"{s.label} · {s.last_event_type}"
                ir = _RECT(PAD + 12, card_y + 28, PAD + card_w - 12, card_y + 42)
                user32.DrawTextW(hdc, info_text, -1, ctypes.byref(ir), DT_LEFT | DT_VCENTER)
                gdi32.SelectObject(hdc, old_f)
                gdi32.DeleteObject(info_font)

                # Message (from raw payload)
                msg = ""
                if s.raw_payload:
                    msg = s.raw_payload.get("message", "")
                if not msg:
                    msg = "请回到 Claude Code 终端查看。"
                gdi32.SetTextColor(hdc, 0x00808080)  # muted
                msg_font = gdi32.CreateFontW(-11, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
                old_f = gdi32.SelectObject(hdc, msg_font)
                mr = _RECT(PAD + 12, card_y + 46, PAD + card_w - 12, card_y + 62)
                user32.DrawTextW(hdc, msg[:60], -1, ctypes.byref(mr), DT_LEFT | DT_VCENTER)
                gdi32.SelectObject(hdc, old_f)
                gdi32.DeleteObject(msg_font)

                self._card_rects.append((card_y, card_y + card_h, s.session_id))
                card_y += card_h + card_gap

        user32.EndPaint(hwnd, ctypes.byref(ps))
