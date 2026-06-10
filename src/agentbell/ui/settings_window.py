"""Settings and About windows for AgentBell.

Dark-themed custom windows using GDI, consistent with the tray menu style.
"""

import ctypes
import ctypes.wintypes
import json
import os
import sys
import time
from pathlib import Path

from agentbell.ui.theme import (
    BG_BGR, DARK_BGR, BG_ELEVATED_BGR, LIGHT_BGR, MID_GRAY_BGR,
    ORANGE_BGR, GREEN_BGR, RED_BGR,
    BORDER_BGR, SEPARATOR_BGR,
    RADIUS_WINDOW,
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
DT_CENTER = 1
DT_VCENTER = 4
DT_SINGLELINE = 0x20
DT_WORDBREAK = 0x10


class _PS(ctypes.Structure):
    _fields_ = [('hdc', ctypes.wintypes.HDC), ('fErase', ctypes.wintypes.BOOL),
                ('rc', ctypes.wintypes.RECT), ('fR', ctypes.wintypes.BOOL),
                ('fI', ctypes.wintypes.BOOL), ('r', ctypes.c_byte * 32)]


class _RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


def _get_settings_path() -> Path:
    return Path(os.environ.get("USERPROFILE", Path.home())) / ".claude" / "settings.json"


def _check_hooks_configured() -> tuple[bool, str]:
    """Check if AgentBell hooks are configured. Returns (is_configured, detail)."""
    settings_path = _get_settings_path()
    if not settings_path.exists():
        return False, "未找到 Claude Code 配置文件"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        hooks = settings.get("hooks", {})
        if not isinstance(hooks, dict):
            return False, "配置文件中无 hooks 设置"
        found_events = []
        for event_type, entries in hooks.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                for hook in entry.get("hooks", []):
                    args = hook.get("args", [])
                    cmd = hook.get("command", "")
                    if "agentbell" in cmd or any("agentbell" in str(a) for a in args):
                        found_events.append(event_type)
        if found_events:
            return True, f"已配置 ({', '.join(found_events)})"
        return False, "未配置 AgentBell hooks"
    except Exception as e:
        return False, f"读取配置失败: {e}"


def _get_settings_content() -> str:
    """Read and return the settings.json content."""
    settings_path = _get_settings_path()
    if not settings_path.exists():
        return "{}"
    try:
        return settings_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"// 读取失败: {e}"


def _install_hooks() -> tuple[bool, str]:
    """Install hooks. Returns (success, message)."""
    try:
        from agentbell.claude_hooks import install_hooks
        backup_path = install_hooks()
        return True, f"Hooks 已安装\n备份: {backup_path}"
    except Exception as e:
        return False, f"安装失败: {e}"


def _uninstall_hooks() -> tuple[bool, str]:
    """Uninstall hooks. Returns (success, message)."""
    try:
        from agentbell.claude_hooks import uninstall_hooks
        uninstall_hooks()
        return True, "Hooks 已移除"
    except Exception as e:
        return False, f"移除失败: {e}"


# ── Settings Window ─────────────────────────────────────────────────────────

WIN_W = 520
WIN_H = 420


class SettingsWindow:
    """Dark-themed settings window for AgentBell."""

    def __init__(self):
        self._hwnd = None
        self._wnd_proc_ref = None
        self._class_name = "AgentBellSettings"
        self._close_rect = [0, 0, 0, 0]
        self._install_rect = [0, 0, 0, 0]
        self._uninstall_rect = [0, 0, 0, 0]
        self._hover_btn = ""
        self._status_msg = ""
        self._is_configured = False

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
                if self._hit_test(x, y, self._close_rect):
                    user32.DestroyWindow(hwnd)
                    return 0
                if self._hit_test(x, y, self._install_rect):
                    self._do_install(hwnd)
                    return 0
                if self._hit_test(x, y, self._uninstall_rect):
                    self._do_uninstall(hwnd)
                    return 0
                return 0
            elif msg == 0x0200:  # WM_MOUSEMOVE
                x = lparam & 0xFFFF
                y = (lparam >> 16) & 0xFFFF
                old = self._hover_btn
                self._hover_btn = ""
                if self._hit_test(x, y, self._install_rect):
                    self._hover_btn = "install"
                elif self._hit_test(x, y, self._uninstall_rect):
                    self._hover_btn = "uninstall"
                elif self._hit_test(x, y, self._close_rect):
                    self._hover_btn = "close"
                if self._hover_btn != old:
                    user32.InvalidateRect(hwnd, None, True)
                IDC_HAND = 32649
                IDC_ARROW = 32512
                user32.SetCursor(user32.LoadCursorW(0, IDC_HAND if self._hover_btn else IDC_ARROW))
                return 0
            elif msg == 0x0020:  # WM_SETCURSOR
                user32.SetCursor(user32.LoadCursorW(0, 32512))
                return 1
            elif msg == 0x0002:  # WM_DESTROY
                self._hwnd = None
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
        wc.hbrBackground = 0
        wc.cr = user32.LoadCursorW(0, 32512)
        user32.RegisterClassW(ctypes.byref(wc))

    def show(self):
        if self._hwnd:
            user32.SetForegroundWindow(self._hwnd)
            return
        self._ensure_class()
        self._is_configured, detail = _check_hooks_configured()
        self._status_msg = detail

        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        x = (sw - WIN_W) // 2
        y = (sh - WIN_H) // 2

        ex = 0x00000008 | 0x00000080  # TOPMOST | TOOLWINDOW
        self._hwnd = user32.CreateWindowExW(
            ex, self._class_name, "AgentBell 设置", 0x00C00000,  # WS_CAPTION | WS_SYSMENU
            x, y, WIN_W, WIN_H, 0, 0, 0, None,
        )
        rgn = gdi32.CreateRoundRectRgn(0, 0, WIN_W + 1, WIN_H + 1,
                                        RADIUS_WINDOW * 2, RADIUS_WINDOW * 2)
        user32.SetWindowRgn(self._hwnd, rgn, True)
        user32.ShowWindow(self._hwnd, 5)
        user32.SetForegroundWindow(self._hwnd)

    def _do_install(self, hwnd):
        ok, msg = _install_hooks()
        self._is_configured, detail = _check_hooks_configured()
        self._status_msg = detail
        if ok:
            self._status_msg = f"{detail}\n{msg}"
        else:
            self._status_msg = msg
        user32.InvalidateRect(hwnd, None, True)

    def _do_uninstall(self, hwnd):
        ok, msg = _uninstall_hooks()
        self._is_configured, detail = _check_hooks_configured()
        self._status_msg = detail
        if not ok:
            self._status_msg = msg
        user32.InvalidateRect(hwnd, None, True)

    @staticmethod
    def _hit_test(x, y, rect):
        return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]

    def _draw_btn(self, hdc, x, y, w, h, text, color, is_hover, rect_store):
        bg = color
        if is_hover:
            r = color & 0xFF
            g = (color >> 8) & 0xFF
            b = (color >> 16) & 0xFF
            r = min(255, r + 30)
            g = min(255, g + 30)
            b = min(255, b + 30)
            bg = (b << 16) | (g << 8) | r
        brush = gdi32.CreateSolidBrush(bg)
        old_b = gdi32.SelectObject(hdc, brush)
        old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
        gdi32.RoundRect(hdc, x, y, x + w, y + h, 8, 8)
        gdi32.SelectObject(hdc, old_b)
        gdi32.SelectObject(hdc, old_p)
        gdi32.DeleteObject(brush)
        gdi32.SetBkMode(hdc, TRANSPARENT)
        gdi32.SetTextColor(hdc, 0x00FFFFFF)
        font = gdi32.CreateFontW(-12, 0, 0, 0, 500, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, font)
        rct = _RECT(x, y, x + w, y + h)
        user32.DrawTextW(hdc, text, -1, ctypes.byref(rct), DT_CENTER | DT_VCENTER | DT_SINGLELINE)
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(font)
        rect_store[:] = [x, y, x + w, y + h]

    def _paint(self, hwnd):
        ps = _PS()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
        rc = _RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rc))
        w, h = rc.right, rc.bottom
        PAD = 20

        # Background
        bg_brush = gdi32.CreateSolidBrush(DARK_BGR)
        user32.FillRect(hdc, ctypes.byref(rc), bg_brush)
        gdi32.DeleteObject(bg_brush)

        # Title
        gdi32.SetBkMode(hdc, TRANSPARENT)
        gdi32.SetTextColor(hdc, LIGHT_BGR)
        title_font = gdi32.CreateFontW(-16, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, title_font)
        tr = _RECT(PAD, PAD, w - PAD - 30, PAD + 24)
        user32.DrawTextW(hdc, "设置", -1, ctypes.byref(tr), DT_LEFT | DT_VCENTER)
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(title_font)

        # Close button
        close_font = gdi32.CreateFontW(-16, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, close_font)
        close_color = ORANGE_BGR if self._hover_btn == "close" else MID_GRAY_BGR
        gdi32.SetTextColor(hdc, close_color)
        cr = _RECT(w - 30, PAD - 2, w - 10, PAD + 18)
        user32.DrawTextW(hdc, "×", -1, ctypes.byref(cr), DT_CENTER | DT_VCENTER)
        self._close_rect = [w - 30, PAD - 2, w - 10, PAD + 18]
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(close_font)

        y = PAD + 36

        # ── Hooks Status Section ──
        section_font = gdi32.CreateFontW(-13, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, section_font)
        gdi32.SetTextColor(hdc, LIGHT_BGR)
        sr = _RECT(PAD, y, w - PAD, y + 20)
        user32.DrawTextW(hdc, "Claude Code Hooks 配置", -1, ctypes.byref(sr), DT_LEFT | DT_VCENTER)
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(section_font)
        y += 28

        # Status dot + text
        dot_color = GREEN_BGR if self._is_configured else RED_BGR
        dot_brush = gdi32.CreateSolidBrush(dot_color)
        old_b = gdi32.SelectObject(hdc, dot_brush)
        old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
        gdi32.Ellipse(hdc, PAD, y + 2, PAD + 8, y + 10)
        gdi32.SelectObject(hdc, old_b)
        gdi32.SelectObject(hdc, old_p)
        gdi32.DeleteObject(dot_brush)

        status_font = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, status_font)
        status_color = GREEN_BGR if self._is_configured else RED_BGR
        gdi32.SetTextColor(hdc, status_color)
        status_label = "已配置" if self._is_configured else "未配置"
        str2 = _RECT(PAD + 14, y, w - PAD, y + 18)
        user32.DrawTextW(hdc, status_label, -1, ctypes.byref(str2), DT_LEFT | DT_VCENTER)
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(status_font)
        y += 24

        # Detail text
        if self._status_msg:
            detail_font = gdi32.CreateFontW(-11, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
            old_f = gdi32.SelectObject(hdc, detail_font)
            gdi32.SetTextColor(hdc, MID_GRAY_BGR)
            dtr = _RECT(PAD, y, w - PAD, y + 36)
            user32.DrawTextW(hdc, self._status_msg, -1, ctypes.byref(dtr), DT_LEFT | DT_WORDBREAK)
            gdi32.SelectObject(hdc, old_f)
            gdi32.DeleteObject(detail_font)
            y += 40

        # Buttons
        btn_w = 100
        btn_h = 32
        btn_gap = 12
        if self._is_configured:
            self._draw_btn(hdc, PAD, y, btn_w, btn_h, "重新安装",
                           ORANGE_BGR, self._hover_btn == "install", self._install_rect)
            self._draw_btn(hdc, PAD + btn_w + btn_gap, y, btn_w, btn_h, "卸载 Hooks",
                           RED_BGR, self._hover_btn == "uninstall", self._uninstall_rect)
        else:
            self._draw_btn(hdc, PAD, y, btn_w, btn_h, "安装 Hooks",
                           ORANGE_BGR, self._hover_btn == "install", self._install_rect)
            self._uninstall_rect[:] = [0, 0, 0, 0]
        y += btn_h + 16

        # Separator
        sep_brush = gdi32.CreateSolidBrush(SEPARATOR_BGR)
        sep_rect = _RECT(PAD, y, w - PAD, y + 1)
        user32.FillRect(hdc, ctypes.byref(sep_rect), sep_brush)
        gdi32.DeleteObject(sep_brush)
        y += 12

        # ── Settings Content Section ──
        section_font2 = gdi32.CreateFontW(-13, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, section_font2)
        gdi32.SetTextColor(hdc, LIGHT_BGR)
        sr2 = _RECT(PAD, y, w - PAD, y + 20)
        user32.DrawTextW(hdc, "settings.json 内容", -1, ctypes.byref(sr2), DT_LEFT | DT_VCENTER)
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(section_font2)
        y += 26

        # Content box
        box_h = h - y - PAD
        if box_h > 20:
            # Background
            box_brush = gdi32.CreateSolidBrush(0x00121211)
            box_rect = _RECT(PAD, y, w - PAD, y + box_h)
            user32.FillRect(hdc, ctypes.byref(box_rect), box_brush)
            gdi32.DeleteObject(box_brush)
            # Border
            border_pen = gdi32.CreatePen(1, 1, SEPARATOR_BGR)
            old_bp = gdi32.SelectObject(hdc, border_pen)
            old_bb = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
            gdi32.RoundRect(hdc, PAD, y, w - PAD, y + box_h, 6, 6)
            gdi32.SelectObject(hdc, old_bp)
            gdi32.SelectObject(hdc, old_bb)
            gdi32.DeleteObject(border_pen)
            # Content
            content = _get_settings_content()
            mono_font = gdi32.CreateFontW(-11, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Cascadia Code')
            old_f = gdi32.SelectObject(hdc, mono_font)
            gdi32.SetTextColor(hdc, 0x00A0A090)
            content_rect = _RECT(PAD + 8, y + 6, w - PAD - 8, y + box_h - 6)
            user32.DrawTextW(hdc, content[:2000], -1, ctypes.byref(content_rect), DT_LEFT | DT_WORDBREAK)
            gdi32.SelectObject(hdc, old_f)
            gdi32.DeleteObject(mono_font)

        user32.EndPaint(hwnd, ctypes.byref(ps))


# ── About Dialog ────────────────────────────────────────────────────────────

ABOUT_W = 380
ABOUT_H = 300


class AboutWindow:
    """Dark-themed About window for AgentBell."""

    def __init__(self):
        self._hwnd = None
        self._wnd_proc_ref = None
        self._class_name = "AgentBellAbout"
        self._close_rect = [0, 0, 0, 0]
        self._hover_close = False

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
                if self._hit_test(x, y, self._close_rect):
                    user32.DestroyWindow(hwnd)
                    return 0
                return 0
            elif msg == 0x0200:  # WM_MOUSEMOVE
                x = lparam & 0xFFFF
                y = (lparam >> 16) & 0xFFFF
                old = self._hover_close
                self._hover_close = self._hit_test(x, y, self._close_rect)
                if self._hover_close != old:
                    user32.InvalidateRect(hwnd, None, True)
                IDC_HAND = 32649
                IDC_ARROW = 32512
                user32.SetCursor(user32.LoadCursorW(0, IDC_HAND if self._hover_close else IDC_ARROW))
                return 0
            elif msg == 0x0020:  # WM_SETCURSOR
                user32.SetCursor(user32.LoadCursorW(0, 32512))
                return 1
            elif msg == 0x0002:  # WM_DESTROY
                self._hwnd = None
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
        wc.hbrBackground = 0
        wc.cr = user32.LoadCursorW(0, 32512)
        user32.RegisterClassW(ctypes.byref(wc))

    def show(self):
        if self._hwnd:
            user32.SetForegroundWindow(self._hwnd)
            return
        self._ensure_class()

        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        x = (sw - ABOUT_W) // 2
        y = (sh - ABOUT_H) // 2

        ex = 0x00000008 | 0x00000080
        self._hwnd = user32.CreateWindowExW(
            ex, self._class_name, "关于 AgentBell", 0x00C00000,
            x, y, ABOUT_W, ABOUT_H, 0, 0, 0, None,
        )
        rgn = gdi32.CreateRoundRectRgn(0, 0, ABOUT_W + 1, ABOUT_H + 1,
                                        RADIUS_WINDOW * 2, RADIUS_WINDOW * 2)
        user32.SetWindowRgn(self._hwnd, rgn, True)
        user32.ShowWindow(self._hwnd, 5)
        user32.SetForegroundWindow(self._hwnd)

    @staticmethod
    def _hit_test(x, y, rect):
        return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]

    def _paint(self, hwnd):
        ps = _PS()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
        rc = _RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rc))
        w, h = rc.right, rc.bottom
        PAD = 24

        # Background
        bg_brush = gdi32.CreateSolidBrush(DARK_BGR)
        user32.FillRect(hdc, ctypes.byref(rc), bg_brush)
        gdi32.DeleteObject(bg_brush)

        gdi32.SetBkMode(hdc, TRANSPARENT)

        # Close button
        close_font = gdi32.CreateFontW(-16, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, close_font)
        close_color = ORANGE_BGR if self._hover_close else MID_GRAY_BGR
        gdi32.SetTextColor(hdc, close_color)
        cr = _RECT(w - 30, PAD - 4, w - 10, PAD + 16)
        user32.DrawTextW(hdc, "×", -1, ctypes.byref(cr), DT_CENTER | DT_VCENTER)
        self._close_rect = [w - 30, PAD - 4, w - 10, PAD + 16]
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(close_font)

        # Orange icon
        icon_sz = 48
        icon_x = (w - icon_sz) // 2
        icon_y = PAD
        icon_brush = gdi32.CreateSolidBrush(ORANGE_BGR)
        old_b = gdi32.SelectObject(hdc, icon_brush)
        old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
        gdi32.RoundRect(hdc, icon_x, icon_y, icon_x + icon_sz, icon_y + icon_sz, 12, 12)
        gdi32.SelectObject(hdc, old_b)
        gdi32.SelectObject(hdc, old_p)
        gdi32.DeleteObject(icon_brush)

        # >_ text in icon
        gdi32.SetTextColor(hdc, 0x00FFFFFF)
        icon_font = gdi32.CreateFontW(-18, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 0, 0, 'Consolas')
        old_f = gdi32.SelectObject(hdc, icon_font)
        icon_rect = _RECT(icon_x, icon_y, icon_x + icon_sz, icon_y + icon_sz)
        user32.DrawTextW(hdc, ">_", -1, ctypes.byref(icon_rect), DT_CENTER | DT_VCENTER)
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(icon_font)

        y = icon_y + icon_sz + 12

        # Title
        gdi32.SetTextColor(hdc, LIGHT_BGR)
        title_font = gdi32.CreateFontW(-18, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, title_font)
        tr = _RECT(PAD, y, w - PAD, y + 26)
        user32.DrawTextW(hdc, "AgentBell", -1, ctypes.byref(tr), DT_CENTER | DT_VCENTER)
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(title_font)
        y += 30

        # Version
        gdi32.SetTextColor(hdc, MID_GRAY_BGR)
        ver_font = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, ver_font)
        vr = _RECT(PAD, y, w - PAD, y + 18)
        user32.DrawTextW(hdc, "v1.0.0", -1, ctypes.byref(vr), DT_CENTER | DT_VCENTER)
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(ver_font)
        y += 26

        # Separator
        sep_brush = gdi32.CreateSolidBrush(SEPARATOR_BGR)
        sep_rect = _RECT(PAD + 40, y, w - PAD - 40, y + 1)
        user32.FillRect(hdc, ctypes.byref(sep_rect), sep_brush)
        gdi32.DeleteObject(sep_brush)
        y += 14

        # Description
        desc_font = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, desc_font)
        gdi32.SetTextColor(hdc, MID_GRAY_BGR)
        lines = [
            "Windows 托盘通知工具",
            "为 Claude Code CLI 提供桌面通知和状态监控",
            "",
            "监听 Claude Code hooks 事件",
            "在系统托盘显示运行状态和授权提醒",
        ]
        for line in lines:
            lr = _RECT(PAD, y, w - PAD, y + 18)
            user32.DrawTextW(hdc, line, -1, ctypes.byref(lr), DT_CENTER | DT_VCENTER)
            y += 18
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(desc_font)
        y += 8

        # Links
        link_font = gdi32.CreateFontW(-11, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        old_f = gdi32.SelectObject(hdc, link_font)
        gdi32.SetTextColor(hdc, ORANGE_BGR)
        links = [
            "GitHub: github.com/anthropics/claude-code",
            "配置文件: ~/.claude/settings.json",
        ]
        for link in links:
            lr = _RECT(PAD, y, w - PAD, y + 16)
            user32.DrawTextW(hdc, link, -1, ctypes.byref(lr), DT_CENTER | DT_VCENTER)
            y += 16
        gdi32.SelectObject(hdc, old_f)
        gdi32.DeleteObject(link_font)

        user32.EndPaint(hwnd, ctypes.byref(ps))
