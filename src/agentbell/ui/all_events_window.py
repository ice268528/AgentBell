"""All Events window for AgentBell.

Shows all events from the event store with scroll support.
Uses Claude/Anthropic warm-dark theme.
"""

import ctypes
import ctypes.wintypes
import sys
import time

from agentbell.ui.theme import (
    BG_BGR, DARK_BGR, BG_ELEVATED_BGR, LIGHT_BGR, MID_GRAY_BGR,
    ORANGE_BGR, GREEN_BGR, BLUE_BGR, RED_BGR,
    BG_CARD_BGR, BG_CARD_HOVER_BGR, BG_HOVER_BGR,
    BG_CARD_LIGHT_BGR, BG_CARD_LIGHT_HOVER_BGR, TEXT_DARK_BGR,
    BORDER_BGR, SEPARATOR_BGR, TEXT_MUTED_BGR,
    GRADIENT_DARK_BGR, GRADIENT_MID_BGR,
    ORANGE_HOVER_BGR,
    RADIUS_WINDOW, RADIUS_CARD, RADIUS_BUTTON,
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

# Scrollbar constants
WM_VSCROLL = 0x0115
WM_MOUSEWHEEL = 0x020A
SB_LINEUP = 0
SB_LINEDOWN = 1
SB_PAGEUP = 2
SB_PAGEDOWN = 3
SB_THUMBPOSITION = 4
SB_THUMBTRACK = 5
SB_ENDSCROLL = 8
SIF_RANGE = 0x0001
SIF_PAGE = 0x0002
SIF_POS = 0x0004
SIF_ALL = SIF_RANGE | SIF_PAGE | SIF_POS


class _PS(ctypes.Structure):
    _fields_ = [('hdc', ctypes.wintypes.HDC), ('fErase', ctypes.wintypes.BOOL),
                ('rc', ctypes.wintypes.RECT), ('fR', ctypes.wintypes.BOOL),
                ('fI', ctypes.wintypes.BOOL), ('r', ctypes.c_byte * 32)]


class _RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class SCROLLINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint),
        ('fMask', ctypes.c_uint),
        ('nMin', ctypes.c_int),
        ('nMax', ctypes.c_int),
        ('nPage', ctypes.c_uint),
        ('nPos', ctypes.c_int),
        ('nTrackPos', ctypes.c_int),
    ]


class AllEventsWindow:
    """All events window with scroll support."""

    def __init__(self, event_store):
        self.event_store = event_store
        self._hwnd = None
        self._visible = False
        self._wnd_proc_ref = None
        self._close_rect = [0, 0, 0, 0]
        self._back_rect = [0, 0, 0, 0]
        self._clear_rect = [0, 0, 0, 0]
        self._card_rects = []
        self._hover_card_idx = -1
        self._scroll_pos = 0
        self._class_name = "AgentBellAllEvents"

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
            elif msg == WM_MOUSEWHEEL:
                # Handle mouse wheel scroll
                delta = ctypes.c_short((wparam >> 16) & 0xFFFF).value
                if delta > 0:
                    self._scroll_up(3)
                else:
                    self._scroll_down(3)
                user32.InvalidateRect(hwnd, None, True)
                return 0
            elif msg == WM_VSCROLL:
                # Handle scrollbar
                event = wparam & 0xFFFF
                if event == SB_LINEUP:
                    self._scroll_up(1)
                elif event == SB_LINEDOWN:
                    self._scroll_down(1)
                elif event == SB_PAGEUP:
                    self._scroll_up(5)
                elif event == SB_PAGEDOWN:
                    self._scroll_down(5)
                elif event == SB_THUMBTRACK or event == SB_THUMBPOSITION:
                    pos = (wparam >> 16) & 0xFFFF
                    self._scroll_to(pos)
                user32.InvalidateRect(hwnd, None, True)
                return 0
            elif msg == 0x0201:  # WM_LBUTTONDOWN
                x = lparam & 0xFFFF
                y = (lparam >> 16) & 0xFFFF
                if self._hit_test(x, y, self._close_rect):
                    self.hide()
                    return 0
                if self._hit_test(x, y, self._back_rect):
                    self.hide()
                    return 0
                if self._hit_test(x, y, self._clear_rect):
                    self.event_store.clear()
                    self._scroll_pos = 0
                    user32.InvalidateRect(hwnd, None, True)
                    return 0
                return 0
            elif msg == 0x0200:  # WM_MOUSEMOVE
                x = lparam & 0xFFFF
                y = (lparam >> 16) & 0xFFFF
                old_hover = self._hover_card_idx
                self._hover_card_idx = -1
                for i, (ct, cb, _) in enumerate(self._card_rects):
                    if ct <= y <= cb:
                        self._hover_card_idx = i
                        break
                if self._hover_card_idx != old_hover:
                    user32.InvalidateRect(hwnd, None, True)
                in_btn = (self._hit_test(x, y, self._close_rect) or
                          self._hit_test(x, y, self._back_rect) or
                          self._hit_test(x, y, self._clear_rect) or
                          self._hover_card_idx >= 0)
                IDC_ARROW = 32512
                IDC_HAND = 32649
                user32.SetCursor(user32.LoadCursorW(0, IDC_HAND if in_btn else IDC_ARROW))
                return 0
            elif msg == 0x0020:  # WM_SETCURSOR
                user32.SetCursor(user32.LoadCursorW(0, 32512))
                return 1
            elif msg == 0x0002:  # WM_DESTROY
                self._visible = False
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
        wc.hCursor = user32.LoadCursorW(0, 32512)
        user32.RegisterClassW(ctypes.byref(wc))

    def _create_window(self):
        """Create the window if it doesn't exist."""
        if self._hwnd:
            return
        self._ensure_class()

        w, h = 480, 600
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        x = sw - w - 24
        y = sh - h - 60

        ex = 0x00000008 | 0x00000080 | 0x08000000  # TOPMOST | TOOLWINDOW | NOACTIVATE
        self._hwnd = user32.CreateWindowExW(
            ex, self._class_name, 'AgentBell - 全部事件', 0x80000000,  # WS_POPUP
            x, y, w, h, 0, 0, 0, None,
        )

        # Apply rounded corner region
        rgn = gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1,
                                        RADIUS_WINDOW * 2, RADIUS_WINDOW * 2)
        user32.SetWindowRgn(self._hwnd, rgn, True)

    def show(self):
        """Show the window."""
        self._create_window()
        self._scroll_pos = 0

        w, h = 480, 600
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        x = sw - w - 24
        y = sh - h - 60

        user32.MoveWindow(self._hwnd, x, y, w, h, True)
        user32.ShowWindow(self._hwnd, 5)
        user32.SetWindowPos(self._hwnd, -1, x, y, w, h, 0x0010 | 0x0040)
        user32.UpdateWindow(self._hwnd)
        user32.InvalidateRect(self._hwnd, None, True)
        self._visible = True

    def hide(self):
        if self._hwnd:
            user32.ShowWindow(self._hwnd, 0)
            self._visible = False

    def _scroll_up(self, lines=1):
        self._scroll_pos = max(0, self._scroll_pos - lines)

    def _scroll_down(self, lines=1):
        events = self.event_store.get_all()
        max_scroll = max(0, len(events) - 5)
        self._scroll_pos = min(max_scroll, self._scroll_pos + lines)

    def _scroll_to(self, pos):
        events = self.event_store.get_all()
        max_scroll = max(0, len(events) - 5)
        self._scroll_pos = min(max_scroll, max(0, pos))

    @staticmethod
    def _hit_test(x, y, rect):
        return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]

    def _draw_rounded_rect(self, hdc, x, y, w, h, r, brush_color, pen_color=None):
        brush = gdi32.CreateSolidBrush(brush_color)
        old_b = gdi32.SelectObject(hdc, brush)
        if pen_color is not None:
            pen = gdi32.CreatePen(1, 1, pen_color)
            old_p = gdi32.SelectObject(hdc, pen)
        else:
            old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
        gdi32.RoundRect(hdc, x, y, x + w, y + h, r, r)
        gdi32.SelectObject(hdc, old_b)
        gdi32.SelectObject(hdc, old_p)
        gdi32.DeleteObject(brush)
        if pen_color is not None:
            gdi32.DeleteObject(pen)

    def _draw_gradient_bg(self, hdc, w, h):
        """Draw vertical dark gradient background."""
        steps = min(h, 64)
        step_h = max(1, h // steps)
        for i in range(steps):
            t = i / max(1, steps - 1)
            r1 = GRADIENT_DARK_BGR & 0xFF
            g1 = (GRADIENT_DARK_BGR >> 8) & 0xFF
            b1 = (GRADIENT_DARK_BGR >> 16) & 0xFF
            r2 = GRADIENT_MID_BGR & 0xFF
            g2 = (GRADIENT_MID_BGR >> 8) & 0xFF
            b2 = (GRADIENT_MID_BGR >> 16) & 0xFF
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            color = (b << 16) | (g << 8) | r
            brush = gdi32.CreateSolidBrush(color)
            rc = _RECT(0, i * step_h, w, min((i + 1) * step_h, h))
            user32.FillRect(hdc, ctypes.byref(rc), brush)
            gdi32.DeleteObject(brush)

    def _paint(self, hwnd):
        ps = _PS()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
        rc = _RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rc))
        w, h = rc.right, rc.bottom

        PAD = 16

        # Gradient background
        self._draw_gradient_bg(hdc, w, h)

        # Window border
        border_pen = gdi32.CreatePen(1, 1, BORDER_BGR)
        old_bp = gdi32.SelectObject(hdc, border_pen)
        old_bb = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
        gdi32.RoundRect(hdc, 0, 0, w, h, RADIUS_WINDOW, RADIUS_WINDOW)
        gdi32.SelectObject(hdc, old_bp)
        gdi32.SelectObject(hdc, old_bb)
        gdi32.DeleteObject(border_pen)

        gdi32.SetBkMode(hdc, TRANSPARENT)

        # Header
        gdi32.SetTextColor(hdc, LIGHT_BGR)
        title_font = gdi32.CreateFontW(-16, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, title_font)
        tr = _RECT(PAD, PAD, w - 60, PAD + 20)
        user32.DrawTextW(hdc, "全部事件", -1, ctypes.byref(tr), DT_LEFT | DT_VCENTER)
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(title_font)

        # Close button
        close_font = gdi32.CreateFontW(-16, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, close_font)
        gdi32.SetTextColor(hdc, MID_GRAY_BGR)
        cr = _RECT(w - 28, PAD - 2, w - 10, PAD + 16)
        user32.DrawTextW(hdc, "×", -1, ctypes.byref(cr), 0x0001 | 0x0004)
        self._close_rect = [w - 28, PAD - 2, w - 10, PAD + 16]
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(close_font)

        # Subtitle
        events = self.event_store.get_all()
        count = len(events)
        t = time.strftime("%H:%M")
        subtitle = f"共 {count} 个事件 · {t}"
        gdi32.SetTextColor(hdc, MID_GRAY_BGR)
        sub_font = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, sub_font)
        sr = _RECT(PAD, PAD + 22, w - 30, PAD + 36)
        user32.DrawTextW(hdc, subtitle, -1, ctypes.byref(sr), DT_LEFT | DT_VCENTER)
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(sub_font)

        # Header separator
        sep_brush = gdi32.CreateSolidBrush(SEPARATOR_BGR)
        sep_rect = _RECT(PAD, PAD + 44, w - PAD, PAD + 45)
        user32.FillRect(hdc, ctypes.byref(sep_rect), sep_brush)
        gdi32.DeleteObject(sep_brush)

        # Event Cards (with scroll)
        self._card_rects = []
        card_y = PAD + 52
        card_w = w - PAD * 2
        card_h = 78
        card_gap = 8

        # Apply scroll offset
        start_idx = self._scroll_pos
        visible_events = events[start_idx:]

        if not events:
            # Empty state
            gdi32.SetTextColor(hdc, LIGHT_BGR)
            title_font = gdi32.CreateFontW(-14, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
            old_tf = gdi32.SelectObject(hdc, title_font)
            title_rect = _RECT(PAD, card_y + 16, w - PAD, card_y + 36)
            user32.DrawTextW(hdc, "暂无事件", -1, ctypes.byref(title_rect), 0x0001 | 0x0004)
            gdi32.SelectObject(hdc, old_tf)
            gdi32.DeleteObject(title_font)
        else:
            for idx, s in enumerate(visible_events):
                if card_y + card_h > h - 60:
                    break

                is_hovered = (idx == self._hover_card_idx)

                # Card background
                if is_hovered:
                    self._draw_rounded_rect(hdc, PAD, card_y, card_w, card_h, RADIUS_CARD,
                                            BG_CARD_LIGHT_HOVER_BGR, ORANGE_HOVER_BGR)
                else:
                    self._draw_rounded_rect(hdc, PAD, card_y, card_w, card_h, RADIUS_CARD,
                                            BG_CARD_LIGHT_BGR, BORDER_BGR)

                # Status dot
                dot_color = STATUS_BGR.get(s.get("kind", ""), MID_GRAY_BGR)
                dot_brush = gdi32.CreateSolidBrush(dot_color)
                old_b = gdi32.SelectObject(hdc, dot_brush)
                old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
                dot_x = PAD + 12
                dot_y = card_y + 14
                gdi32.Ellipse(hdc, dot_x, dot_y, dot_x + 8, dot_y + 8)
                gdi32.SelectObject(hdc, old_b)
                gdi32.SelectObject(hdc, old_p)
                gdi32.DeleteObject(dot_brush)

                # Line 1: Status label + Timestamp
                state_label = STATE_LABELS.get(s.get("kind", ""), s.get("kind", ""))
                gdi32.SetTextColor(hdc, TEXT_DARK_BGR)
                label_font = gdi32.CreateFontW(-12, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
                old_f = gdi32.SelectObject(hdc, label_font)
                lr = _RECT(dot_x + 14, card_y + 12, card_w - 80, card_y + 26)
                user32.DrawTextW(hdc, state_label, -1, ctypes.byref(lr), DT_LEFT | DT_VCENTER)

                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s.get("timestamp", 0)))
                gdi32.SetTextColor(hdc, MID_GRAY_BGR)
                ts_rect = _RECT(card_w - 140, card_y + 12, card_w - 10, card_y + 26)
                user32.DrawTextW(hdc, ts, -1, ctypes.byref(ts_rect), DT_RIGHT | DT_VCENTER)
                gdi32.SelectObject(hdc, old_f)
                gdi32.DeleteObject(label_font)

                # Line 2: Project name
                gdi32.SetTextColor(hdc, 0x00404040)
                info_font = gdi32.CreateFontW(-12, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
                old_f = gdi32.SelectObject(hdc, info_font)
                project_name = s.get('session_label', 'Unknown')
                ir = _RECT(dot_x + 14, card_y + 30, card_w - 12, card_y + 44)
                user32.DrawTextW(hdc, project_name, -1, ctypes.byref(ir), DT_LEFT | DT_VCENTER)
                gdi32.SelectObject(hdc, old_f)
                gdi32.DeleteObject(info_font)

                # Line 3: Description
                kind = s.get("kind", "")
                msg_fallbacks = {
                    "permission_required": "需要你确认工具调用以继续执行。",
                    "waiting_input": "本轮响应已结束，请回到终端继续操作。",
                    "task_completed": "任务已标记完成。请回到终端查看输出或继续操作。",
                    "error": "发生错误。请回到 Claude Code 终端查看详细信息。",
                    "info": "请回到 Claude Code 终端查看。",
                }
                msg = msg_fallbacks.get(kind, "请回到 Claude Code 终端查看。")
                gdi32.SetTextColor(hdc, 0x00808080)
                msg_font = gdi32.CreateFontW(-11, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
                old_f = gdi32.SelectObject(hdc, msg_font)
                mr = _RECT(dot_x + 14, card_y + 48, card_w - 12, card_y + 64)
                user32.DrawTextW(hdc, msg[:80], -1, ctypes.byref(mr), DT_LEFT | DT_VCENTER)
                gdi32.SelectObject(hdc, old_f)
                gdi32.DeleteObject(msg_font)

                self._card_rects.append((card_y, card_y + card_h, s.get("session_id", "")))
                card_y += card_h + card_gap

        # Footer
        footer_y = h - 44

        sep_brush2 = gdi32.CreateSolidBrush(SEPARATOR_BGR)
        sep_rect2 = _RECT(PAD, footer_y - 2, w - PAD, footer_y - 1)
        user32.FillRect(hdc, ctypes.byref(sep_rect2), sep_brush2)
        gdi32.DeleteObject(sep_brush2)

        gdi32.SetBkMode(hdc, TRANSPARENT)
        btn_h = 28
        btn_font = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')

        old_bf = gdi32.SelectObject(hdc, btn_font)

        # Back button
        gdi32.SetTextColor(hdc, MID_GRAY_BGR)
        back_rect = _RECT(PAD, footer_y, PAD + 60, footer_y + btn_h)
        user32.DrawTextW(hdc, "← 返回", -1, ctypes.byref(back_rect), DT_LEFT | DT_VCENTER)
        self._back_rect = [PAD, footer_y, PAD + 60, footer_y + btn_h]

        # Clear button
        gdi32.SetTextColor(hdc, RED_BGR)
        clear_rect = _RECT(w - PAD - 60, footer_y, w - PAD, footer_y + btn_h)
        user32.DrawTextW(hdc, "清空", -1, ctypes.byref(clear_rect), DT_RIGHT | DT_VCENTER)
        self._clear_rect = [w - PAD - 60, footer_y, w - PAD, footer_y + btn_h]

        # Scroll indicator
        if events:
            scroll_text = f"{start_idx + 1}-{min(start_idx + 5, count)} / {count}"
            gdi32.SetTextColor(hdc, MID_GRAY_BGR)
            scroll_rect = _RECT(w // 2 - 40, footer_y, w // 2 + 40, footer_y + btn_h)
            user32.DrawTextW(hdc, scroll_text, -1, ctypes.byref(scroll_rect), DT_VCENTER | 0x0001)

        gdi32.SelectObject(hdc, old_bf)
        gdi32.DeleteObject(btn_font)

        user32.EndPaint(hwnd, ctypes.byref(ps))
