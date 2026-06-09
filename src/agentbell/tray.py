"""System tray icon for AgentBell daemon.

Uses custom UI components:
- Custom tray icon (not system default info icon)
- Custom dark-themed context menu (not system default popup)
- Custom dark-themed recent events window (not QMessageBox)
"""

import ctypes
import ctypes.wintypes
import os
import sys
import threading
import time

from agentbell.logging_utils import setup_logging
from agentbell.ui.icons import create_default_icon, create_badge_icon, create_muted_icon
from agentbell.ui.tray_menu import TrayMenu, ID_RECENT, ID_MUTE, ID_QUIT, ID_SETTINGS, ID_ABOUT
from agentbell.ui.recent_events_window import RecentEventsWindow

logger = setup_logging()

# ── Windows constants ────────────────────────────────────────────────────────
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 1
WM_DESTROY = 0x0002

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_ICON = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_TIP = 0x00000004

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32

LRESULT = ctypes.c_longlong if sys.maxsize > 2**32 else ctypes.c_long
LP = ctypes.c_longlong if sys.maxsize > 2**32 else ctypes.c_long


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
        ("szInfo", ctypes.wintypes.WCHAR * 128),
        ("uTimeoutOrVersion", ctypes.c_uint32),
        ("szInfoTitle", ctypes.wintypes.WCHAR * 64),
        ("dwInfoFlags", ctypes.c_uint32),
        ("guidItem", GUID),
        ("hBalloonIcon", ctypes.wintypes.HICON),
    ]


class TrayIcon:
    """System tray icon with custom UI."""

    def __init__(self, daemon):
        self.daemon = daemon
        self._hwnd = None
        self._nid = None
        self._wnd_proc_ref = None
        self._class_name = "AgentBellTrayClass"
        self._default_icon = None
        self._badge_icon = None
        self._muted_icon = None
        self._is_muted = False

        # Custom UI components
        self.recent_events = RecentEventsWindow(daemon)
        self.menu = TrayMenu(daemon, on_action=self._on_menu_action)

    def _create_window(self):
        """Create a hidden window for tray icon messages."""
        user32.DefWindowProcW.argtypes = [ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, LP]
        user32.DefWindowProcW.restype = LRESULT

        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, LP)

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_TRAYICON:
                if lparam == 0x0204:  # WM_RBUTTONDOWN
                    self.menu.show()
                elif lparam == 0x0201:  # WM_LBUTTONDOWN
                    self.recent_events.toggle()
                elif lparam == 0x0203:  # WM_LBUTTONDBLCLK
                    self.recent_events.toggle()
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
        """Add tray icon with custom icon."""
        # Create custom icons
        self._default_icon = create_default_icon(16)
        self._badge_icon = create_badge_icon(16, 1)
        self._muted_icon = create_muted_icon(16)

        self._nid = NOTIFYICONDATAW()
        self._nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self._nid.hWnd = self._hwnd
        self._nid.uID = 1
        self._nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP
        self._nid.uCallbackMessage = WM_TRAYICON
        self._nid.hIcon = self._default_icon
        self._nid.szTip = "AgentBell"
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid))

    def _update_icon(self, icon_handle):
        """Update tray icon."""
        if self._nid:
            self._nid.hIcon = icon_handle
            self._nid.uFlags = NIF_ICON
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))
            self._nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP

    def _update_tooltip(self, text: str):
        if self._nid:
            self._nid.szTip = text[:63]
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))

    def _on_menu_action(self, item_id: int):
        """Handle menu item click."""
        if item_id == ID_RECENT:
            self.recent_events.show()
        elif item_id == ID_MUTE:
            self._toggle_mute()
        elif item_id == ID_QUIT:
            self._quit()

    def _toggle_mute(self):
        if self.daemon.is_muted():
            self.daemon._muted_until = 0
            self._is_muted = False
            self._update_icon(self._default_icon)
            self._update_tooltip("AgentBell")
        else:
            self.daemon.mute(30)
            self._is_muted = True
            self._update_icon(self._muted_icon)
            self._update_tooltip("AgentBell (已静音)")

    def _quit(self):
        if self._nid:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
        if self._default_icon:
            user32.DestroyIcon(self._default_icon)
        if self._badge_icon:
            user32.DestroyIcon(self._badge_icon)
        if self._muted_icon:
            user32.DestroyIcon(self._muted_icon)
        user32.DestroyWindow(self._hwnd)

    def update_badge(self):
        """Update tray icon based on pending events."""
        count = self.daemon.registry.get_pending_permission_count()
        if self._is_muted:
            self._update_icon(self._muted_icon)
            self._update_tooltip("AgentBell (已静音)")
        elif count > 0:
            # Create badge icon with count
            badge = create_badge_icon(16, count)
            self._update_icon(badge)
            self._update_tooltip(f"AgentBell ({count} 个等待授权)")
            # Clean up old badge icon
            if self._badge_icon:
                user32.DestroyIcon(self._badge_icon)
            self._badge_icon = badge
        else:
            self._update_icon(self._default_icon)
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
