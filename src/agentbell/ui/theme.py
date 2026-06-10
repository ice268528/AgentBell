"""Unified Claude/Anthropic design tokens for all AgentBell UI.

Reference: https://github.com/anthropics/skills/blob/main/skills/brand-guidelines/SKILL.md

Design language:
- Dark warm background (#181816)
- Orange accent (#d97757) for interactive elements
- Card-based layouts with subtle borders
- Large corner radii (18px windows, 14px cards)
- Muted secondary text for hierarchy
"""


def hex_to_bgr(hex_color: str) -> int:
    """Convert '#RRGGBB' to 0x00BBGGRR for GDI."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# ── Base colors ──────────────────────────────────────────────────────────────
DARK = "#141413"
BG = "#181816"
BG_ELEVATED = "#20201d"
LIGHT = "#faf9f5"
MID_GRAY = "#b0aea5"
LIGHT_GRAY = "#e8e6dc"
ORANGE = "#d97757"
ORANGE_HOVER = "#e38a6b"
ORANGE_PRESSED = "#c76645"
GREEN = "#788c5d"
BLUE = "#6a9bcc"
RED = "#c45f4f"

# Gradient stops (for header backgrounds)
GRADIENT_DARK = "#141413"
GRADIENT_MID = "#181816"
GRADIENT_LIGHT = "#1E1E1B"

# ── Derived ──────────────────────────────────────────────────────────────────
TEXT_PRIMARY = LIGHT
TEXT_SECONDARY = MID_GRAY
TEXT_MUTED = "rgba(250,249,245,0.58)"

BORDER = "rgba(250,249,245,0.12)"
BORDER_SOFT = "rgba(250,249,245,0.08)"

BG_CARD = "rgba(250,249,245,0.055)"
BG_CARD_HOVER = "rgba(250,249,245,0.075)"
BG_HOVER = "rgba(250,249,245,0.065)"
BG_ACTIVE = "rgba(217,119,87,0.12)"

# ── BGR values for GDI ──────────────────────────────────────────────────────
BG_BGR = hex_to_bgr(BG)
DARK_BGR = hex_to_bgr(DARK)
BG_ELEVATED_BGR = hex_to_bgr(BG_ELEVATED)
LIGHT_BGR = hex_to_bgr(LIGHT)
MID_GRAY_BGR = hex_to_bgr(MID_GRAY)
ORANGE_BGR = hex_to_bgr(ORANGE)
GREEN_BGR = hex_to_bgr(GREEN)
BLUE_BGR = hex_to_bgr(BLUE)
RED_BGR = hex_to_bgr(RED)
TEXT_PRIMARY_BGR = LIGHT_BGR
TEXT_SECONDARY_BGR = MID_GRAY_BGR

# Card colors (approximated as solid BGR)
BG_CARD_BGR = 0x00161514
BG_CARD_HOVER_BGR = 0x001A1918
BG_HOVER_BGR = 0x00191817
BG_ACTIVE_BGR = 0x00182A29

# Gradient BGR (approximated)
GRADIENT_DARK_BGR = hex_to_bgr(GRADIENT_DARK)
GRADIENT_MID_BGR = hex_to_bgr(GRADIENT_MID)
GRADIENT_LIGHT_BGR = hex_to_bgr(GRADIENT_LIGHT)

# Orange accent BGR variants
ORANGE_HOVER_BGR = hex_to_bgr(ORANGE_HOVER)
ORANGE_PRESSED_BGR = hex_to_bgr(ORANGE_PRESSED)

# Text muted BGR (approximated from rgba(250,249,245,0.58))
TEXT_MUTED_BGR = 0x008C8B87

# Border BGR (approximated from rgba(250,249,245,0.12))
BORDER_BGR = 0x001E1D1C
BORDER_SOFT_BGR = 0x00141312

# Separator BGR
SEPARATOR_BGR = 0x001A1918

# ── Status colors ────────────────────────────────────────────────────────────
STATUS_COLORS = {
    "permission_required": ORANGE,
    "waiting_input": BLUE,
    "task_completed": GREEN,
    "error": RED,
    "info": MID_GRAY,
    "running": GREEN,
    "background_running": MID_GRAY,
}

STATUS_BGR = {k: hex_to_bgr(v) for k, v in STATUS_COLORS.items()}

# ── State labels ─────────────────────────────────────────────────────────────
STATE_LABELS = {
    "running": "运行中",
    "waiting_permission": "等待授权",
    "waiting_input": "等待输入",
    "background_running": "后台运行",
    "task_completed": "已完成",
    "error": "错误",
}

# ── Radius ───────────────────────────────────────────────────────────────────
RADIUS_WINDOW = 18
RADIUS_CARD = 14
RADIUS_BUTTON = 10
RADIUS_ICON = 12
RADIUS_PILL = 999

# ── Spacing ──────────────────────────────────────────────────────────────────
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24

# ── Font ─────────────────────────────────────────────────────────────────────
FONT_FAMILY = 'Segoe UI, Microsoft YaHei UI, sans-serif'
FONT_MONO = 'Cascadia Code, Consolas, monospace'

# ── Window dimensions ────────────────────────────────────────────────────────
RECENT_EVENTS_W = 840
RECENT_EVENTS_H = 520
RECENT_EVENTS_MIN_H = 280
TRAY_MENU_W = 380
TRAY_MENU_MIN_H = 320

# ── Panel dimensions ────────────────────────────────────────────────────────
HEADER_H_PANEL = 68     # brand header in tray panel
ITEM_H_PANEL = 68       # menu item height in tray panel
ITEM_H_MENU = 42        # compact menu item height
SEPARATOR_H = 8
PADDING_PANEL = 12

# ── Toast dimensions ────────────────────────────────────────────────────────
TOAST_W = 440
TOAST_H_COMPACT = 150
TOAST_H_EXPANDED = 260

# ── Shadow tokens (simulated via layered drawing) ──────────────────────────
SHADOW_COLOR = 0x00000000  # pure black for shadow simulation
SHADOW_BLUR = 24
