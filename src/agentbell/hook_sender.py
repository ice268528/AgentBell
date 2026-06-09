"""Lightweight hook sender - reads JSON from stdin, sends to daemon.

Used as Claude Code hook command. Reads hook JSON from stdin,
sends to local daemon via HTTP, then exits immediately.
Does not display UI. Does not run long.
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
    from agentbell.daemon import is_daemon_running, DAEMON_URL
    if is_daemon_running():
        return True

    # Try to start daemon
    try:
        python_dir = os.path.dirname(sys.executable)
        pythonw = os.path.join(python_dir, "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable

        # Start daemon in background
        subprocess.Popen(
            [pythonw, "-m", "agentbell", "daemon"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
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


def send_hook_event(event_name: str, payload: dict) -> bool:
    """Send a hook event to the daemon."""
    from agentbell.daemon import send_to_daemon
    return send_to_daemon(event_name, payload)


def main():
    """Entry point for hook sender. Reads JSON from stdin."""
    # Suppress stdout/stderr to not pollute Claude Code
    devnull = open(os.devnull, "w")
    sys.stdout = devnull
    sys.stderr = devnull

    # Read JSON from stdin
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        payload = json.loads(raw)
    except (json.JSONDecodeError, IOError):
        return

    # Determine event name
    event_name = payload.get("hook_event_name", "")
    if not event_name:
        event_name = payload.get("hook_type", "")

    if not event_name:
        return

    # Ensure daemon is running
    if not _start_daemon_if_needed():
        logger.error("Daemon not available, event lost: %s", event_name)
        return

    # Send to daemon
    send_hook_event(event_name, payload)


if __name__ == "__main__":
    main()
