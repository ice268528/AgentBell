"""Claude-styled toast notification with full interactivity.

Supports three states:
- Compact: default view with title, description, buttons
- Expanded: shows detail panel with tool/command/project info
- Mini Pill: auto-collapses after 10s, click to re-expand

Uses ctypes + GDI for rendering. No PowerShell dependency.
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
    LIGHT,
    MID_GRAY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TOAST_BG,
    TOAST_BG_ELEVATED,
    AgentBellConfig,
    ClaudeHookToastEvent,
)

logger = setup_logging()


def _hex_to_bgr(hex_color: str) -> int:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _generate_toast_script(event: ClaudeHookToastEvent, config: AgentBellConfig | None = None) -> str:
    cfg = config or AgentBellConfig()
    accent = _hex_to_bgr(event.accent_color)
    bg = _hex_to_bgr(TOAST_BG)
    bg_elevated = _hex_to_bgr(TOAST_BG_ELEVATED)
    title_color = _hex_to_bgr(TEXT_PRIMARY)
    desc_color = _hex_to_bgr(TEXT_SECONDARY)
    eyebrow_color = _hex_to_bgr(MID_GRAY)
    icon_bg = _hex_to_bgr(ACCENT_PRESSED)
    icon_fg = _hex_to_bgr(LIGHT)
    accent_hover = _hex_to_bgr(ACCENT_HOVER)

    title = event.title or {
        "permission_required": "Claude Code 需要授权",
        "task_done": "Claude Code 任务完成",
        "error": "Claude Code 执行失败",
        "info": "Claude Code 通知",
    }.get(event.type, "Claude Code 通知")

    desc = event.message or {
        "permission_required": "需要你确认工具调用以继续执行。",
        "task_done": "当前任务已完成。",
        "error": "执行过程中出现错误。",
        "info": "",
    }.get(event.type, "")

    eyebrow = {
        "permission_required": "等待授权",
        "task_done": "已完成",
        "error": "错误",
        "info": "通知",
    }.get(event.type, "通知")

    primary_btn = {
        "permission_required": "打开 Claude Code",
        "task_done": "查看结果",
        "error": "查看错误",
        "info": "打开 Claude Code",
    }.get(event.type, "打开 Claude Code")

    secondary_btn = "查看详情" if event.tool_name or event.command else "忽略"

    # Detail info
    tool_name = event.tool_name or ""
    command = event.command or ""
    project_path = event.project_path or ""

    auto_collapse_ms = cfg.auto_collapse_ms

    return f'''import ctypes, ctypes.wintypes, sys, time, winsound, threading

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

POINT = ctypes.wintypes.POINT

# ── Data ──
title = "{_esc(title)}"
desc = "{_esc(desc)}"
eyebrow = "{_esc(eyebrow)}"
primary_text = "{_esc(primary_btn)}"
secondary_text = "{_esc(secondary_btn)}"
tool_name = "{_esc(tool_name)}"
cmd_text = "{_esc(command)}"
proj_path = "{_esc(project_path)}"
accent = {accent}
accent_hover = {accent_hover}
bg = {bg}
bg_elevated = {bg_elevated}
title_color = {title_color}
desc_color = {desc_color}
eyebrow_color = {eyebrow_color}
icon_bg = {icon_bg}
icon_fg = {icon_fg}
duration = {auto_collapse_ms // 1000 + 12}

# ── State ──
state = "compact"  # compact | expanded | pill
hwnd_ref = [0]
pill_hwnd_ref = [0]

# ── Layout constants ──
COMPACT_W, COMPACT_H = 380, 130
EXPANDED_W, EXPANDED_H = 400, 220
PILL_W, PILL_H = 160, 36
PAD = 16
ICON_SZ = 36

# Button rects (relative to window)
btn_primary_rect = [0, 0, 0, 0]
btn_secondary_rect = [0, 0, 0, 0]
btn_close_rect = [0, 0, 0, 0]
btn_pill_rect = [0, 0, 0, 0]

def pt_in_rect(px, py, r):
    return r[0] <= px <= r[2] and r[1] <= py <= r[3]

def draw_rounded_rect(hdc, x, y, w, h, r):
    gdi32.RoundRect(hdc, x, y, x+w, y+h, r, r)

def draw_compact(hdc, w, h):
    # Background
    bg_brush = gdi32.CreateSolidBrush(bg)
    rc = RECT(0, 0, w, h)
    user32.FillRect(hdc, ctypes.byref(rc), bg_brush)
    gdi32.DeleteObject(bg_brush)

    # Accent bar
    ab = gdi32.CreateSolidBrush(accent)
    bar = RECT(0, 0, w, 3)
    user32.FillRect(hdc, ctypes.byref(bar), ab)
    gdi32.DeleteObject(ab)

    # Icon
    ib = gdi32.CreateSolidBrush(icon_bg)
    old_b = gdi32.SelectObject(hdc, ib)
    old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(0))
    draw_rounded_rect(hdc, PAD, 20, ICON_SZ, ICON_SZ, 10)
    gdi32.SelectObject(hdc, old_b)
    gdi32.SelectObject(hdc, old_p)
    gdi32.DeleteObject(ib)
    gdi32.SetBkMode(hdc, 1)
    gdi32.SetTextColor(hdc, icon_fg)
    f = gdi32.CreateFontW(-14, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
    o = gdi32.SelectObject(hdc, f)
    ir = RECT(PAD, 20, PAD+ICON_SZ, 20+ICON_SZ)
    user32.DrawTextW(hdc, '>_', -1, ctypes.byref(ir), 0x0001 | 0x0004)
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(f)

    # Eyebrow
    gdi32.SetTextColor(hdc, eyebrow_color)
    mf = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
    o = gdi32.SelectObject(hdc, mf)
    # Dot
    db = gdi32.CreateSolidBrush(accent)
    ob = gdi32.SelectObject(hdc, db)
    gdi32.Ellipse(hdc, 66, 24, 73, 31)
    gdi32.SelectObject(hdc, ob)
    gdi32.DeleteObject(db)
    er = RECT(80, 20, w-30, 34)
    user32.DrawTextW(hdc, eyebrow, -1, ctypes.byref(er), 0)
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(mf)

    # Close button
    gdi32.SetTextColor(hdc, eyebrow_color)
    cf = gdi32.CreateFontW(-16, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
    o = gdi32.SelectObject(hdc, cf)
    cr = RECT(w-28, 10, w-10, 28)
    user32.DrawTextW(hdc, '\\u00d7', -1, ctypes.byref(cr), 0x0001 | 0x0004)
    btn_close_rect[:] = [w-28, 10, w-10, 28]
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(cf)

    # Title
    gdi32.SetTextColor(hdc, title_color)
    tf = gdi32.CreateFontW(-15, 0, 0, 0, 650, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
    o = gdi32.SelectObject(hdc, tf)
    tr = RECT(66, 36, w-20, 56)
    user32.DrawTextW(hdc, title, -1, ctypes.byref(tr), 0)
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(tf)

    # Description
    if desc:
        gdi32.SetTextColor(hdc, desc_color)
        df = gdi32.CreateFontW(-13, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
        o = gdi32.SelectObject(hdc, df)
        dr = RECT(66, 56, w-20, 78)
        user32.DrawTextW(hdc, desc, -1, ctypes.byref(dr), 0)
        gdi32.SelectObject(hdc, o)
        gdi32.DeleteObject(df)

    # Buttons
    btn_y = h - 38
    # Primary button
    px = w - 130
    pw = 110
    pb = gdi32.CreateSolidBrush(accent)
    old_b = gdi32.SelectObject(hdc, pb)
    old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(0))
    draw_rounded_rect(hdc, px, btn_y, pw, 28, 8)
    gdi32.SelectObject(hdc, old_b)
    gdi32.SelectObject(hdc, old_p)
    gdi32.DeleteObject(pb)
    gdi32.SetTextColor(hdc, icon_fg)
    pf = gdi32.CreateFontW(-12, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
    o = gdi32.SelectObject(hdc, pf)
    pr = RECT(px, btn_y, px+pw, btn_y+28)
    user32.DrawTextW(hdc, primary_text, -1, ctypes.byref(pr), 0x0001 | 0x0004)
    btn_primary_rect[:] = [px, btn_y, px+pw, btn_y+28]
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(pf)

    # Secondary button
    sx = px - 90
    sw = 80
    gdi32.SetTextColor(hdc, title_color)
    sf = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
    o = gdi32.SelectObject(hdc, sf)
    sr = RECT(sx, btn_y, sx+sw, btn_y+28)
    user32.DrawTextW(hdc, secondary_text, -1, ctypes.byref(sr), 0x0002 | 0x0004)  # DT_RIGHT | DT_VCENTER
    btn_secondary_rect[:] = [sx, btn_y, sx+sw, btn_y+28]
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(sf)


def draw_expanded(hdc, w, h):
    draw_compact(hdc, w, h)  # Base
    # Detail panel
    dy = 90
    dh = h - dy - 44
    db = gdi32.CreateSolidBrush(bg_elevated)
    old_b = gdi32.SelectObject(hdc, db)
    old_p = gdi32.SelectObject(hdc, gdi32.GetStockObject(0))
    draw_rounded_rect(hdc, PAD, dy, w - PAD*2, dh, 10)
    gdi32.SelectObject(hdc, old_b)
    gdi32.SelectObject(hdc, old_p)
    gdi32.DeleteObject(db)

    gdi32.SetBkMode(hdc, 1)
    gdi32.SetTextColor(hdc, title_color)
    lf = gdi32.CreateFontW(-12, 0, 0, 0, 600, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
    o = gdi32.SelectObject(hdc, lf)
    lr = RECT(PAD+10, dy+8, w-PAD-10, dy+24)
    user32.DrawTextW(hdc, '将执行以下操作', -1, ctypes.byref(lr), 0)
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(lf)

    gdi32.SetTextColor(hdc, desc_color)
    vf = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
    o = gdi32.SelectObject(hdc, vf)
    vr = RECT(PAD+10, dy+26, w-PAD-10, dy+42)
    detail_text = tool_name or cmd_text or proj_path or '工具调用详情暂不可用'
    user32.DrawTextW(hdc, detail_text, -1, ctypes.byref(vr), 0)
    if cmd_text:
        gdi32.SetTextColor(hdc, accent)
        cf = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Consolas')
        o2 = gdi32.SelectObject(hdc, cf)
        cr = RECT(PAD+10, dy+44, w-PAD-10, dy+60)
        user32.DrawTextW(hdc, cmd_text, -1, ctypes.byref(cr), 0)
        gdi32.SelectObject(hdc, o2)
        gdi32.DeleteObject(cf)
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(vf)


def draw_pill(hdc, w, h):
    bg_brush = gdi32.CreateSolidBrush(bg_elevated)
    rc = RECT(0, 0, w, h)
    user32.FillRect(hdc, ctypes.byref(rc), bg_brush)
    gdi32.DeleteObject(bg_brush)

    # Dot
    db = gdi32.CreateSolidBrush(accent)
    old_b = gdi32.SelectObject(hdc, db)
    gdi32.Ellipse(hdc, 14, 14, 22, 22)
    gdi32.SelectObject(hdc, old_b)
    gdi32.DeleteObject(db)

    # Text
    gdi32.SetBkMode(hdc, 1)
    gdi32.SetTextColor(hdc, eyebrow_color)
    tf = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, 'Segoe UI')
    o = gdi32.SelectObject(hdc, tf)
    tr = RECT(28, 0, w-10, h)
    user32.DrawTextW(hdc, eyebrow, -1, ctypes.byref(tr), 0x0004)  # DT_VCENTER
    gdi32.SelectObject(hdc, o)
    gdi32.DeleteObject(tf)
    btn_pill_rect[:] = [0, 0, w, h]


def paint(hwnd):
    ps = PS()
    hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
    rc = RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rc))
    w = rc.right
    h = rc.bottom
    if state == "compact":
        draw_compact(hdc, w, h)
    elif state == "expanded":
        draw_expanded(hdc, w, h)
    elif state == "pill":
        draw_pill(hdc, w, h)
    user32.EndPaint(hwnd, ctypes.byref(ps))


# Custom messages for state transitions (handled outside WNDPROC)
WM_COLLAPSE = 0x0400 + 100  # WM_USER + 100
WM_EXPAND = 0x0400 + 101
WM_RESTORE = 0x0400 + 102

def _resize_window(new_state, w, h):
    global state
    state = new_state
    hwnd = hwnd_ref[0]
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    user32.MoveWindow(hwnd, sw - w - 24, sh - h - 60, w, h, True)
    user32.InvalidateRect(hwnd, None, True)


def wp(h, ms, wp, lp):
    if ms == 0x000F:  # WM_PAINT
        paint(h)
        return 0
    elif ms == 0x0201:  # WM_LBUTTONDOWN
        x = lp & 0xFFFF
        y = (lp >> 16) & 0xFFFF
        if state == "pill":
            user32.PostMessageW(h, WM_RESTORE, 0, 0)
            return 0
        if pt_in_rect(x, y, btn_close_rect):
            user32.DestroyWindow(h)
            return 0
        if pt_in_rect(x, y, btn_primary_rect):
            user32.DestroyWindow(h)
            return 0
        if pt_in_rect(x, y, btn_secondary_rect):
            if state == "compact" and (tool_name or cmd_text or proj_path):
                user32.PostMessageW(h, WM_EXPAND, 0, 0)
            else:
                user32.DestroyWindow(h)
            return 0
        return 0
    elif ms == 0x0200:  # WM_MOUSEMOVE
        x = lp & 0xFFFF
        y = (lp >> 16) & 0xFFFF
        in_btn = pt_in_rect(x, y, btn_primary_rect) or pt_in_rect(x, y, btn_secondary_rect) or pt_in_rect(x, y, btn_close_rect) or pt_in_rect(x, y, btn_pill_rect)
        IDC_ARROW = 32512
        IDC_HAND = 32649
        user32.SetCursor(user32.LoadCursorW(0, IDC_HAND if in_btn else IDC_ARROW))
        return 0
    elif ms == 0x0020:  # WM_SETCURSOR
        user32.SetCursor(user32.LoadCursorW(0, 32512))
        return 1
    elif ms == 0x0113:  # WM_TIMER
        if state != "pill":
            user32.PostMessageW(h, WM_COLLAPSE, 0, 0)
        return 0
    elif ms == 0x0002:  # WM_DESTROY
        user32.PostQuitMessage(0)
        return 0
    elif ms == WM_COLLAPSE:
        _resize_window("pill", PILL_W, PILL_H)
        return 0
    elif ms == WM_EXPAND:
        _resize_window("expanded", EXPANDED_W, EXPANDED_H)
        return 0
    elif ms == WM_RESTORE:
        _resize_window("compact", COMPACT_W, COMPACT_H)
        user32.SetTimer(h, 1, {auto_collapse_ms}, None)
        return 0
    return user32.DefWindowProcW(h, ms, wp, lp)

# Sound
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
user32.RegisterClassW(ctypes.byref(w))

sw = user32.GetSystemMetrics(0)
sh = user32.GetSystemMetrics(1)

ex = 0x00000008 | 0x00000080 | 0x08000000
h = user32.CreateWindowExW(ex, 'ClaudeToast', 'AgentBell', 0x80000000,
    sw - COMPACT_W - 24, sh - COMPACT_H - 60, COMPACT_W, COMPACT_H, 0, 0, 0, None)
hwnd_ref[0] = h
user32.ShowWindow(h, 5)
user32.SetWindowPos(h, -1, sw - COMPACT_W - 24, sh - COMPACT_H - 60, COMPACT_W, COMPACT_H, 0x0010 | 0x0040)
user32.UpdateWindow(h)
user32.SetTimer(h, 1, {auto_collapse_ms}, None)

msg = ctypes.wintypes.MSG()
while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0):
    user32.TranslateMessage(ctypes.byref(msg))
    user32.DispatchMessageW(ctypes.byref(msg))
'''


# ── Toast registry for stacking ──────────────────────────────────────────────
_TOAST_DIR = os.path.join(tempfile.gettempdir(), "agentbell_toasts")
os.makedirs(_TOAST_DIR, exist_ok=True)


def _cleanup_old_toasts():
    """Remove stale toast markers (older than 30s)."""
    now = time.time()
    for f in os.listdir(_TOAST_DIR):
        path = os.path.join(_TOAST_DIR, f)
        try:
            if now - os.path.getmtime(path) > 30:
                os.unlink(path)
        except OSError:
            pass


def _get_active_toast_count() -> int:
    """Count active toast marker files."""
    _cleanup_old_toasts()
    return len([f for f in os.listdir(_TOAST_DIR) if f.endswith(".toast")])


def _register_toast(toast_id: str) -> str:
    """Register a toast and return its marker path."""
    marker = os.path.join(_TOAST_DIR, f"{toast_id}.toast")
    with open(marker, "w") as f:
        f.write(str(time.time()))
    return marker


def _unregister_toast(marker_path: str) -> None:
    """Remove a toast marker."""
    try:
        os.unlink(marker_path)
    except OSError:
        pass


def show_toast(
    event: ClaudeHookToastEvent,
    config: AgentBellConfig | None = None,
    duration: int = 12,
) -> None:
    cfg = config or AgentBellConfig()
    logger.info("Showing toast: type=%r, title=%r", event.type, event.title)

    # Dedup: check if same event type was shown recently
    _cleanup_old_toasts()
    for f in os.listdir(_TOAST_DIR):
        if f.endswith(".toast"):
            marker = os.path.join(_TOAST_DIR, f)
            try:
                mtime = os.path.getmtime(marker)
                if time.time() - mtime < cfg.dedupe_window_ms / 1000:
                    # Check if it's the same event type
                    if event.type in f:
                        logger.info("Dedup: skipping %s (shown recently)", event.type)
                        return
            except OSError:
                pass

    # Stacking: limit to max_visible_toasts
    active = _get_active_toast_count()
    if active >= cfg.max_visible_toasts:
        logger.info("Max toasts reached (%d), skipping", cfg.max_visible_toasts)
        return

    # Register this toast
    toast_id = f"{event.type}_{event.id}"
    marker_path = _register_toast(toast_id)

    script = _generate_toast_script(event, cfg)

    # Calculate Y offset for stacking (each toast is offset by COMPACT_H + gap)
    y_offset = active * (130 + 8)

    # Inject Y offset into the script
    script = script.replace(
        f"sh - COMPACT_H - 60",
        f"sh - COMPACT_H - 60 - {y_offset}"
    ).replace(
        f"sh - PILL_H - 60",
        f"sh - PILL_H - 60 - {y_offset}"
    ).replace(
        f"sh - EXPANDED_H - 60",
        f"sh - EXPANDED_H - 60 - {y_offset}"
    )

    script_path = os.path.join(tempfile.gettempdir(), f"agentbell_toast_{uuid.uuid4().hex[:8]}.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    try:
        subprocess.Popen(
            [pythonw, script_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Toast subprocess launched.")
    except Exception as e:
        logger.error("Failed to launch toast: %s", e)

    def cleanup():
        time.sleep(duration + 2)
        try:
            os.unlink(script_path)
        except OSError:
            pass
        _unregister_toast(marker_path)

    threading.Thread(target=cleanup, daemon=True).start()


def show_permission_toast(
    title: str | None = None,
    message: str | None = None,
    tool_name: str | None = None,
    command: str | None = None,
    project_path: str | None = None,
    config: AgentBellConfig | None = None,
) -> None:
    event = ClaudeHookToastEvent(
        id=uuid.uuid4().hex[:12],
        type="permission_required",
        title=title,
        message=message,
        tool_name=tool_name,
        command=command,
        project_path=project_path,
    )
    show_toast(event, config)


def show_done_toast(
    title: str | None = None,
    message: str | None = None,
    config: AgentBellConfig | None = None,
) -> None:
    event = ClaudeHookToastEvent(
        id=uuid.uuid4().hex[:12],
        type="task_done",
        title=title,
        message=message,
    )
    show_toast(event, config)
