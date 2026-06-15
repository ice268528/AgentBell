"""AgentBell entry point for PyInstaller build.

Runs the daemon with tray icon. No console window.
"""

import sys
import os

# Ensure src/agentbell is importable
if getattr(sys, 'frozen', False):
    # PyInstaller: add _internal to path so agentbell package is found
    internal = os.path.join(sys._MEIPASS)
    if internal not in sys.path:
        sys.path.insert(0, internal)
else:
    src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

from agentbell.daemon import DaemonServer, is_daemon_running
from agentbell.tray import run_with_tray


def main():
    # Toast daemon mode (started by toast_pipe_client)
    if "--toast-daemon" in sys.argv:
        from agentbell.toast_daemon import run_toast_daemon
        run_toast_daemon()
        return

    # Main daemon mode
    if is_daemon_running():
        sys.exit(0)

    srv = DaemonServer()
    run_with_tray(srv)


if __name__ == "__main__":
    main()
