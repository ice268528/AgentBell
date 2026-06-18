"""Install/uninstall Claude Code hooks for AgentBell.

Hooks use `hook-sender` command which reads JSON from stdin
and forwards to the daemon. No direct toast creation.
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
    1. Frozen exe: AgentBell.exe (supports CLI mode)
    2. agentbell on PATH (e.g. via uv tool install)
    3. .venv/Scripts/agentbell.exe in the project directory (uv sync)
    4. uv run agentbell as fallback
    """
    import shutil as _shutil
    import sys

    # 1. Check if running as frozen exe
    if getattr(sys, 'frozen', False):
        # Use the current executable (AgentBell.exe supports CLI mode)
        return (str(sys.executable), [])

    # 2. Check PATH
    found = _shutil.which("agentbell")
    if found:
        return (found, [])

    # 3. Check .venv in project directory
    project_dir = Path(__file__).resolve().parent.parent.parent
    venv_exe = project_dir / ".venv" / "Scripts" / "agentbell.exe"
    if venv_exe.exists():
        return (str(venv_exe), [])

    # 4. Fallback: uv run
    return ("uv", ["run", "--directory", str(project_dir), "agentbell"])


def _make_hook_entry(command: str, base_args: list[str], matcher: str = "") -> dict:
    """Create a hook entry that uses hook-sender.

    hook-sender reads Claude Code hook JSON from stdin
    and forwards to the daemon via HTTP.
    """
    args = base_args + ["hook-sender"]
    return {
        "matcher": matcher,
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
        cmd_lower = cmd.lower()
        if "agentbell" in cmd_lower or any("agentbell" in str(a).lower() for a in args):
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

    # PermissionRequest hook → daemon handles routing
    perm_entries = hooks.get("PermissionRequest", [])
    perm_entries = _filter_agentbell_entries(perm_entries)
    perm_entries.append(_make_hook_entry(command, base_args))
    hooks["PermissionRequest"] = perm_entries
    logger.info("Updated PermissionRequest hook")

    # Notification + idle_prompt hook → daemon handles routing
    notif_entries = hooks.get("Notification", [])
    notif_entries = _filter_agentbell_entries(notif_entries)
    notif_entries.append(_make_hook_entry(command, base_args, matcher="idle_prompt"))
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
