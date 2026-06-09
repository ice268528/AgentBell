"""System tray icon for AgentBell daemon.

Uses ctypes + Windows API to create a tray icon with context menu.
No external dependencies.
"""

import ctypes
import ctypes.wintypes
import os
import sys
import threading
import time

from agentbell.logging_utils import setup_logging

logger = setup_logging()

# ── Windows constants ────────────────────────────────────────────────────────
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 1
WM_COMMAND = 0x0111
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_ICON = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIIF_INFO = 0x00000001

MF_STRING = 0x00000000
MF_GRAYED = 0x00000001
MF_SEPARATOR = 0x00000800
TPM_RIGHTBUTTON = 0x00000002
TPM_BOTTOMALIGN = 0x00000020

GCL_WNDPROC = -24
GWLP_WNDPROC = -4

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32

LRESULT = ctypes.c_longlong if sys.maxsize > 2**32 else ctypes.c_long
LP = ctypes.c_longlong if sys.maxsize > 2**32 else ctypes.c_long


# ── NOTIFYICONDATAW ──────────────────────────────────────────────────────────
class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_uint8 * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("hWnd", ctypes.wintypes.HWND),
        ("uID", ctypes.c_uint32),
        ("uFlags", ctypes.c_uint32),
        ("uCallbackMessage", ctypes.c_uint32),
        ("hIcon", ctypes.wintypes.HICON),
        ("szTip", ctypes.c_wchar * 64),
        ("dwState", ctypes.c_uint32),
        ("dwStateMask", ctypes.c_uint32),
        ("szInfo", ctypes.c_wchar * 128),
        ("uTimeoutOrVersion", ctypes.c_uint32),
        ("szInfoTitle", ctypes.c_wchar * 64),
        ("dwInfoFlags", ctypes.c_uint32),
        ("guidItem", GUID),
        ("hBalloonIcon", ctypes.wintypes.HICON),
    ]


# ── Menu IDs ─────────────────────────────────────────────────────────────────
ID_RECENT = 1001
ID_MUTE = 1002
ID_SETTINGS = 1003
ID_QUIT = 1004


class TrayIcon:
    """System tray icon with context menu."""

    def __init__(self, daemon):
        self.daemon = daemon
        self._hwnd = None
        self._nid = None
        self._icon = None
        self._wnd_proc_ref = None
        self._class_name = "AgentBellTrayClass"
        self._badge_count = 0

    def _create_window(self):
        """Create a hidden window for tray icon messages."""
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, LP)

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_TRAYICON:
                if lparam == 0x0204:  # WM_RBUTTONDOWN
                    self._show_menu(hwnd)
                elif lparam == 0x0203:  # WM_LBUTTONDBLCLK
                    self._show_recent_events()
                return 0
            elif msg == WM_COMMAND:
                cmd_id = wparam & 0xFFFF
                if cmd_id == ID_RECENT:
                    self._show_recent_events()
                elif cmd_id == ID_MUTE:
                    self._toggle_mute()
                elif cmd_id == ID_SETTINGS:
                    self._show_settings()
                elif cmd_id == ID_QUIT:
                    self._quit()
                return 0
            elif msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wnd_proc_ref = WNDPROC(wnd_proc)

        class WNDCLASS(ctypes.Structure):
            _fields_ = [("style", ctypes.c_uint), ("lpfnWndProc", WNDPROC),
                        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                        ("hInstance", ctypes.wintypes.HINSTANCE), ("hIcon", ctypes.wintypes.HICON),
                        ("hCursor", ctypes.wintypes.HANDLE), ("hbrBackground", ctypes.wintypes.HANDLE),
                        ("lpszMenuName", ctypes.wintypes.LPCWSTR), ("lpszClassName", ctypes.wintypes.LPCWSTR)]

        wc = WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc_ref
        wc.lpszClassName = self._class_name
        user32.RegisterClassW(ctypes.byref(wc))

        self._hwnd = user32.CreateWindowExW(
            0, self._class_name, "AgentBell", 0,
            0, 0, 0, 0, 0, 0, 0, None,
        )

    def _add_tray_icon(self):
        """Add tray icon to system tray."""
        self._nid = NOTIFYICONDATAW()
        self._nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self._nid.hWnd = self._hwnd
        self._nid.uID = 1
        self._nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP
        self._nid.uCallbackMessage = WM_TRAYICON
        self._nid.hIcon = user32.LoadIconW(0, 32516)  # IDI_INFORMATION
        self._nid.szTip = "AgentBell"
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid))

    def _update_tooltip(self, text: str):
        """Update tray icon tooltip."""
        if self._nid:
            self._nid.szTip = text[:63]
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))

    def _show_balloon(self, title: str, msg: str):
        """Show a balloon notification from tray icon."""
        if self._nid:
            self._nid.szInfoTitle = title[:63]
            self._nid.szInfo = msg[:127]
            self._nid.dwInfoFlags = NIIF_INFO
            self._nid.uFlags = NIF_INFO
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))
            self._nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP

    def _show_menu(self, hwnd):
        """Show context menu at cursor position."""
        menu = user32.CreatePopupMenu()

        # Recent events
        user32.AppendMenuW(menu, MF_STRING, ID_RECENT, "最近事件")

        # Mute
        mute_text = "取消静音" if self.daemon.is_muted() else "静音 30 分钟"
        user32.AppendMenuW(menu, MF_STRING, ID_MUTE, mute_text)

        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)

        # Quit
        user32.AppendMenuW(menu, MF_STRING, ID_QUIT, "退出 AgentBell")

        # Show at cursor position
        point = ctypes.wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        user32.TrackPopupMenu(
            menu, TPM_RIGHTBUTTON | TPM_BOTTOMALIGN,
            point.x, point.y, 0, hwnd, None,
        )
        user32.DestroyMenu(menu)

    def _show_recent_events(self):
        """Show recent events in a message box."""
        sessions = self.daemon.registry.get_all()
        if not sessions:
            text = "暂无事件记录"
        else:
            lines = []
            for s in sessions[-10:]:  # last 10
                state_emoji = {
                    "running": "[运行中]",
                    "waiting_permission": "[等待授权]",
                    "waiting_input": "[等待输入]",
                    "background_running": "[后台运行]",
                    "task_completed": "[已完成]",
                    "error": "[错误]",
                }.get(s.state, "[未知]")
                lines.append(f"{state_emoji} {s.label} - {s.last_event_type}")
            text = "\n".join(lines)

        user32.MessageBoxW(0, text, "AgentBell 最近事件", 0x00000040)  # MB_ICONINFORMATION

    def _toggle_mute(self):
        """Toggle mute state."""
        if self.daemon.is_muted():
            self.daemon._muted_until = 0
            self._update_tooltip("AgentBell")
        else:
            self.daemon.mute(30)
            self._update_tooltip("AgentBell (已静音)")

    def _show_settings(self):
        """Show settings (placeholder)."""
        user32.MessageBoxW(0, "设置功能开发中", "AgentBell", 0x00000040)

    def _quit(self):
        """Quit the daemon."""
        if self._nid:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
        user32.DestroyWindow(self._hwnd)

    def update_badge(self):
        """Update tray icon badge based on pending events."""
        count = self.daemon.registry.get_pending_permission_count()
        if count > 0:
            tip = f"AgentBell ({count} 个等待授权)"
            self._update_tooltip(tip)
        else:
            self._update_tooltip("AgentBell")

    def run(self):
        """Run the tray icon message loop (blocking)."""
        self._create_window()
        self._add_tray_icon()

        # Start daemon in background thread
        daemon_thread = threading.Thread(target=self.daemon.start, daemon=True)
        daemon_thread.start()

        # Set up tray callback
        self.daemon.set_tray_callback(self.update_badge)

        logger.info("Tray icon started")

        # Message loop
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        logger.info("Tray icon exited")


def run_with_tray(daemon):
    """Run daemon with tray icon."""
    tray = TrayIcon(daemon)
    tray.run()
