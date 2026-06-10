"""Claude / Anthropic official color tokens and UI constants.

Reference: https://github.com/anthropics/skills/blob/main/skills/brand-guidelines/SKILL.md
"""

from dataclasses import dataclass, field
from typing import Literal


# ── Base colors ──────────────────────────────────────────────────────────────
DARK = "#141413"
LIGHT = "#faf9f5"
MID_GRAY = "#b0aea5"
LIGHT_GRAY = "#e8e6dc"
ORANGE = "#d97757"
BLUE = "#6a9bcc"
GREEN = "#788c5d"

# ── Toast extended colors ────────────────────────────────────────────────────
TOAST_BG = "#181816"
TOAST_BG_ELEVATED = "#20201d"
TOAST_BORDER = "rgba(250, 249, 245, 0.12)"
TOAST_BORDER_STRONG = "rgba(217, 119, 87, 0.42)"

TEXT_PRIMARY = "#faf9f5"
TEXT_SECONDARY = "#b0aea5"
TEXT_MUTED = "rgba(250, 249, 245, 0.58)"

ACCENT_PRIMARY = "#d97757"
ACCENT_HOVER = "#e38a6b"
ACCENT_PRESSED = "#c76645"
RED = "#c75050"

CODE_BG = "rgba(250, 249, 245, 0.06)"
CODE_BORDER = "rgba(250, 249, 245, 0.1)"

SHADOW_SOFT = "0 18px 48px rgba(0, 0, 0, 0.38)"
SHADOW_ORANGE = "0 0 32px rgba(217, 119, 87, 0.18)"

# ── Event accent colors ─────────────────────────────────────────────────────
EVENT_COLORS = {
    "permission_required": ORANGE,  # 橙色 - 等待授权
    "waiting_input": BLUE,          # 蓝色 - 等待输入
    "task_done": GREEN,             # 绿色 - 任务完成
    "error": RED,                   # 红色 - 错误
    "info": MID_GRAY,               # 灰色 - 普通通知
}

# ── Radius ───────────────────────────────────────────────────────────────────
RADIUS_TOAST = 16
RADIUS_CARD = 12
RADIUS_BUTTON = 10
RADIUS_PILL = 999

# ── Font ─────────────────────────────────────────────────────────────────────
FONT_FAMILY = (
    '"Microsoft YaHei UI", "Segoe UI", "PingFang SC", '
    "Inter, ui-sans-serif, system-ui, sans-serif"
)
FONT_MONO = '"Cascadia Code", "Consolas", "Liberation Mono", monospace'

FONT_TITLE = 15
FONT_BODY = 13
FONT_META = 12
FONT_CODE = 12

# ── Timing ───────────────────────────────────────────────────────────────────
ANIMATION_DURATION_MS = 180
AUTO_COLLAPSE_MS = 10000
DEDUPE_WINDOW_MS = 3000
MAX_VISIBLE_TOASTS = 3


# ── Event data model ─────────────────────────────────────────────────────────
@dataclass
class ClaudeHookToastEvent:
    """Unified event object for toast notifications."""

    id: str = ""
    type: Literal["permission_required", "task_done", "error", "info", "waiting_input"] = "info"
    title: str | None = None
    message: str | None = None
    tool_name: str | None = None
    command: str | None = None
    project_path: str | None = None
    session_id: str | None = None
    timestamp: float = field(default_factory=lambda: __import__("time").time())
    priority: Literal["low", "normal", "high"] = "normal"

    @property
    def accent_color(self) -> str:
        return EVENT_COLORS.get(self.type, BLUE)


# ── Config defaults ──────────────────────────────────────────────────────────
@dataclass
class AgentBellConfig:
    """User-configurable settings."""

    theme: str = "claude-dark"
    position: str = "bottom-right"
    always_on_top: bool = True
    steal_focus: bool = False
    play_sound: bool = True
    auto_collapse_ms: int = AUTO_COLLAPSE_MS
    max_visible_toasts: int = MAX_VISIBLE_TOASTS
    dedupe_window_ms: int = DEDUPE_WINDOW_MS
    show_command_preview: bool = True
    show_project_path: bool = True
    sound_volume: float = 0.45
