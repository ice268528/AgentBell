"""Lightweight hook sender - reads Claude Code hook JSON from stdin, sends to daemon.

Used as Claude Code hook command. Reads hook JSON from stdin,
sends to local daemon via HTTP, then exits immediately.
Does not display UI. Does not run long.
If daemon is not running, tries to start it (max 500ms).
"""

import json
import os
import subprocess
import sys
import time

from agentbell.logging_utils import setup_logging

logger = setup_logging()


def _start_daemon_if_needed() -> bool:
    """Try to start daemon if not running. Wait up to 500ms."""
    from agentbell.daemon import is_daemon_running
    if is_daemon_running():
        return True

    try:
        if getattr(sys, 'frozen', False):
            # Frozen exe: launch AgentBell.exe (GUI daemon) from same directory
            exe_dir = os.path.dirname(sys.executable)
            gui_exe = os.path.join(exe_dir, "AgentBell.exe")
            if not os.path.exists(gui_exe):
                # Fallback: check parent directory (CLI might be in AgentBell/ subfolder)
                gui_exe = os.path.join(os.path.dirname(exe_dir), "AgentBell.exe")
            if os.path.exists(gui_exe):
                subprocess.Popen(
                    [gui_exe],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                )
            else:
                logger.error("AgentBell.exe not found near %s", exe_dir)
                return False
        else:
            # Development: use pythonw to start daemon
            python_dir = os.path.dirname(sys.executable)
            pythonw = os.path.join(python_dir, "pythonw.exe")
            if not os.path.exists(pythonw):
                pythonw = sys.executable
            subprocess.Popen(
                [pythonw, "-m", "agentbell", "daemon"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,
            )
    except Exception as e:
        logger.error("Failed to start daemon: %s", e)
        return False

    # Wait for daemon to be ready (max 500ms)
    for _ in range(10):
        time.sleep(0.05)
        if is_daemon_running():
            return True

    return False


def main():
    """Entry point for hook sender. Reads JSON from stdin, sends to daemon."""
    # Suppress stdout/stderr to not pollute Claude Code
    devnull = open(os.devnull, "w")
    sys.stdout = devnull
    sys.stderr = devnull

    # Read JSON from stdin (Claude Code passes hook event data on stdin)
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        payload = json.loads(raw)
    except (json.JSONDecodeError, IOError) as e:
        logger.error("Failed to read stdin JSON: %s", e)
        return

    # Determine event name from payload
    event_name = payload.get("hook_event_name", "")
    if not event_name:
        event_name = payload.get("hook_type", "")

    if not event_name:
        logger.warning("No event name in payload, skipping")
        return

    # Ensure daemon is running
    if not _start_daemon_if_needed():
        logger.error("Daemon not available, event lost: %s", event_name)
        return

    # Send to daemon
    from agentbell.daemon import send_to_daemon
    success = send_to_daemon(event_name, payload)
    if not success:
        logger.error("Failed to send event to daemon: %s", event_name)


if __name__ == "__main__":
    main()
