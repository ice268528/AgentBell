"""Install/uninstall Claude Code hooks for AgentBell.

Claude Code hooks format in settings.json:
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": "",
        "hooks": [
          {"type": "command", "command": "...", "args": [...], "async": true}
        ]
      }
    ],
    "Notification": [
      {
        "matcher": "idle_prompt",
        "hooks": [
          {"type": "command", "command": "...", "args": [...], "async": true}
        ]
      }
    ]
  }
}
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from agentbell.logging_utils import setup_logging

logger = setup_logging()


def _get_settings_path() -> Path:
    return Path(os.environ.get("USERPROFILE", Path.home())) / ".claude" / "settings.json"


def _get_agentbell_command() -> tuple[str, list[str]]:
    """Return (command, base_args) for invoking agentbell.

    Priority:
    1. agentbell on PATH (e.g. via uv tool install)
    2. .venv/Scripts/agentbell.exe in the project directory (uv sync)
    3. uv run agentbell as fallback
    """
    import shutil as _shutil

    # 1. Check PATH
    found = _shutil.which("agentbell")
    if found:
        return (found, [])

    # 2. Check .venv in project directory
    project_dir = Path(__file__).resolve().parent.parent.parent
    venv_exe = project_dir / ".venv" / "Scripts" / "agentbell.exe"
    if venv_exe.exists():
        return (str(venv_exe), [])

    # 3. Fallback: uv run
    return ("uv", ["run", "--directory", str(project_dir), "agentbell"])


def _make_permission_hook_entry(command: str, base_args: list[str]) -> dict:
    """Create a PermissionRequest hook entry."""
    args = base_args + [
        "notify",
        "--title", "Claude Code 需要授权",
        "--message", "需要你确认工具调用以继续执行。",
        "--kind", "permission",
        "--source", "claude-code",
    ]
    return {
        "matcher": "",
        "hooks": [
            {
                "type": "command",
                "command": command,
                "args": args,
                "async": True,
            }
        ],
    }


def _make_notification_hook_entry(command: str, base_args: list[str]) -> dict:
    """Create a Notification + idle_prompt hook entry.

    idle_prompt means Claude Code is waiting for user input,
    NOT that a task is completed.
    """
    args = base_args + [
        "notify",
        "--title", "Claude Code 等待输入",
        "--message", "本轮响应已结束，请回到终端继续操作。",
        "--kind", "waiting_input",
        "--source", "claude-code",
    ]
    return {
        "matcher": "idle_prompt",
        "hooks": [
            {
                "type": "command",
                "command": command,
                "args": args,
                "async": True,
            }
        ],
    }


def _is_agentbell_hook_entry(entry: dict) -> bool:
    """Check if a matcher entry contains AgentBell hooks."""
    for hook in entry.get("hooks", []):
        args = hook.get("args", [])
        cmd = hook.get("command", "")
        if "agentbell" in cmd or any("agentbell" in str(a) for a in args):
            return True
    return False


def _filter_agentbell_entries(entries: list) -> list:
    """Remove AgentBell hook entries from a list of matcher entries."""
    return [e for e in entries if not _is_agentbell_hook_entry(e)]


def install_hooks() -> Path:
    """Install AgentBell hooks into Claude Code settings.json.

    Returns the backup file path.
    """
    settings_path = _get_settings_path()

    # Read existing settings or start fresh
    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read settings.json, starting fresh: %s", e)

    # Backup
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = settings_path.parent / f"settings.backup.{timestamp}.json"
    if settings_path.exists():
        shutil.copy2(settings_path, backup_path)
        logger.info("Backed up settings to %s", backup_path)

    # Ensure hooks dict exists
    hooks: dict = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}

    # Get the agentbell command
    command, base_args = _get_agentbell_command()
    logger.info("Using agentbell command: %s, base_args: %s", command, base_args)

    # Build new hook entries
    permission_entry = _make_permission_hook_entry(command, base_args)
    notification_entry = _make_notification_hook_entry(command, base_args)

    # Update PermissionRequest hooks
    perm_entries = hooks.get("PermissionRequest", [])
    perm_entries = _filter_agentbell_entries(perm_entries)
    perm_entries.append(permission_entry)
    hooks["PermissionRequest"] = perm_entries
    logger.info("Updated PermissionRequest hook")

    # Update Notification hooks
    notif_entries = hooks.get("Notification", [])
    notif_entries = _filter_agentbell_entries(notif_entries)
    notif_entries.append(notification_entry)
    hooks["Notification"] = notif_entries
    logger.info("Updated Notification hook")

    settings["hooks"] = hooks

    # Write back
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Installed hooks to %s", settings_path)

    return backup_path


def uninstall_hooks() -> None:
    """Remove AgentBell hooks from Claude Code settings.json."""
    settings_path = _get_settings_path()

    if not settings_path.exists():
        logger.info("No settings.json found, nothing to uninstall.")
        return

    try:
        settings: dict = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read settings.json: %s", e)
        return

    hooks: dict = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        logger.info("No hooks dict found, nothing to uninstall.")
        return

    removed = 0
    for event_type in list(hooks.keys()):
        entries = hooks[event_type]
        if not isinstance(entries, list):
            continue
        filtered = _filter_agentbell_entries(entries)
        if len(filtered) < len(entries):
            removed += len(entries) - len(filtered)
            hooks[event_type] = filtered

    if removed == 0:
        logger.info("No AgentBell hooks found to remove.")
        return

    # Clean up empty event type arrays
    for event_type in list(hooks.keys()):
        if not hooks[event_type]:
            del hooks[event_type]

    settings["hooks"] = hooks
    settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Removed %d AgentBell hook(s) from %s", removed, settings_path)
