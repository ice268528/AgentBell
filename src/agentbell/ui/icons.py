"""Custom tray icon generation using GDI.

Generates HICON for system tray with:
- Default: dark circle + orange ">_" terminal symbol
- Badge: red/orange dot with count
- Muted: dimmed version
"""

import ctypes
import ctypes.wintypes
import sys

from agentbell.ui.theme import (
    DARK_BGR, ORANGE_BGR, ORANGE, LIGHT_BGR, RED_BGR, GREEN_BGR,
    hex_to_bgr, hex_to_rgb,
)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


def _create_icon_from_bitmap(width: int, height: int, bg_bgr: int, fg_bgr: int,
                              symbol: str = ">_", badge_count: int = 0,
                              muted: bool = False) -> int:
    """Create an HICON from a GDI bitmap.

    Args:
        width: Icon width (16, 24, 32, etc.)
        height: Icon height
        bg_bgr: Background color in BGR
        fg_bgr: Foreground color in BGR
        symbol: Text to draw (e.g. ">_")
        badge_count: Number to show as badge (0 = no badge)
        muted: If True, draw with reduced opacity

    Returns:
        HICON handle
    """
    # Create DC and bitmap
    hdc = user32.GetDC(0)
    mem_dc = gdi32.CreateCompatibleDC(hdc)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ('biSize', ctypes.c_uint32),
            ('biWidth', ctypes.c_long),
            ('biHeight', ctypes.c_long),
            ('biPlanes', ctypes.c_uint16),
            ('biBitCount', ctypes.c_uint16),
            ('biCompression', ctypes.c_uint32),
            ('biSizeImage', ctypes.c_uint32),
            ('biXPelsPerMeter', ctypes.c_long),
            ('biYPelsPerMeter', ctypes.c_long),
            ('biClrUsed', ctypes.c_uint32),
            ('biClrImportant', ctypes.c_uint32),
        ]

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = width
    bmi.biHeight = -height  # top-down
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0  # BI_RGB

    bits = ctypes.c_void_p()
    hbitmap = gdi32.CreateDIBSection(
        hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0
    )
    old_bmp = gdi32.SelectObject(mem_dc, hbitmap)

    # Draw background (circle)
    bg_brush = gdi32.CreateSolidBrush(bg_bgr)
    old_brush = gdi32.SelectObject(mem_dc, bg_brush)
    old_pen = gdi32.SelectObject(mem_dc, gdi32.GetStockObject(5))  # NULL_PEN
    gdi32.Ellipse(mem_dc, 0, 0, width, height)
    gdi32.SelectObject(mem_dc, old_brush)
    gdi32.SelectObject(mem_dc, old_pen)
    gdi32.DeleteObject(bg_brush)

    # Draw ">_" symbol
    font_size = max(8, int(height * 0.5))
    font = gdi32.CreateFontW(
        font_size, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI'
    )
    old_font = gdi32.SelectObject(mem_dc, font)
    gdi32.SetBkMode(mem_dc, 1)  # TRANSPARENT
    gdi32.SetTextColor(mem_dc, fg_bgr if not muted else (fg_bgr & 0x00FFFFFF) // 2 + (0x00404040))

    # Center text
    rect = ctypes.wintypes.RECT(0, 0, width, height)
    user32.DrawTextW(mem_dc, symbol, -1, ctypes.byref(rect),
                     0x0001 | 0x0004)  # DT_CENTER | DT_VCENTER

    gdi32.SelectObject(mem_dc, old_font)
    gdi32.DeleteObject(font)

    # Draw badge if count > 0
    if badge_count > 0:
        badge_r = max(3, width // 4)
        badge_x = width - badge_r * 2 - 1
        badge_y = 1

        badge_brush = gdi32.CreateSolidBrush(RED_BGR)
        old_b = gdi32.SelectObject(mem_dc, badge_brush)
        old_p = gdi32.SelectObject(mem_dc, gdi32.GetStockObject(5))
        gdi32.Ellipse(mem_dc, badge_x, badge_y, badge_x + badge_r * 2, badge_y + badge_r * 2)
        gdi32.SelectObject(mem_dc, old_b)
        gdi32.SelectObject(mem_dc, old_p)
        gdi32.DeleteObject(badge_brush)

        # Badge number
        badge_text = str(badge_count) if badge_count <= 9 else "9+"
        badge_font_size = max(6, badge_r)
        badge_font = gdi32.CreateFontW(
            badge_font_size, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI'
        )
        old_f = gdi32.SelectObject(mem_dc, badge_font)
        gdi32.SetTextColor(mem_dc, LIGHT_BGR)
        badge_rect = ctypes.wintypes.RECT(badge_x, badge_y, badge_x + badge_r * 2, badge_y + badge_r * 2)
        user32.DrawTextW(mem_dc, badge_text, -1, ctypes.byref(badge_rect),
                         0x0001 | 0x0004)
        gdi32.SelectObject(mem_dc, old_f)
        gdi32.DeleteObject(badge_font)

    # Create mask bitmap (all zeros for 32-bit with alpha)
    mask = gdi32.CreateBitmap(width, height, 1, 1, None)

    # Create icon
    class ICONINFO(ctypes.Structure):
        _fields_ = [
            ('fIcon', ctypes.wintypes.BOOL),
            ('xHotspot', ctypes.c_uint32),
            ('yHotspot', ctypes.c_uint32),
            ('hbmMask', ctypes.wintypes.HBITMAP),
            ('hbmColor', ctypes.wintypes.HBITMAP),
        ]

    icon_info = ICONINFO()
    icon_info.fIcon = True
    icon_info.hbmMask = mask
    icon_info.hbmColor = hbitmap
    hicon = user32.CreateIconIndirect(ctypes.byref(icon_info))

    # Cleanup
    gdi32.DeleteObject(mask)
    gdi32.SelectObject(mem_dc, old_bmp)
    gdi32.DeleteObject(hbitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(0, hdc)

    return hicon


def create_default_icon(size: int = 16) -> int:
    """Create default tray icon: dark circle + orange '>_'."""
    return _create_icon_from_bitmap(
        size, size,
        bg_bgr=hex_to_bgr("#2a2a28"),
        fg_bgr=ORANGE_BGR,
        symbol=">_",
    )


def create_badge_icon(size: int = 16, count: int = 1) -> int:
    """Create tray icon with unread badge."""
    return _create_icon_from_bitmap(
        size, size,
        bg_bgr=hex_to_bgr("#2a2a28"),
        fg_bgr=ORANGE_BGR,
        symbol=">_",
        badge_count=count,
    )


def create_muted_icon(size: int = 16) -> int:
    """Create muted tray icon (dimmed)."""
    return _create_icon_from_bitmap(
        size, size,
        bg_bgr=hex_to_bgr("#1a1a18"),
        fg_bgr=hex_to_bgr("#606058"),
        symbol=">_",
        muted=True,
    )
