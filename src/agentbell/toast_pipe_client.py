"""Lightweight pipe client for sending toast requests to the daemon.

Uses Windows Named Pipe for ~1ms latency vs ~50ms for subprocess-based toast creation.
"""

import ctypes
import ctypes.wintypes
import json
import logging
import os
import subprocess
import sys
import time

logger = logging.getLogger("agentbell.toast_pipe_client")

# ── Pipe constants ───────────────────────────────────────────────────────────
PIPE_NAME = "\\\\.\\pipe\\agentbell_toast"
INVALID_HANDLE_VALUE = -1
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
CREATE_NO_WINDOW = 0x08000000

kernel32 = ctypes.windll.kernel32


def _connect_pipe() -> int | None:
    """Try to connect to the toast daemon pipe. Returns handle or None."""
    handle = kernel32.CreateFileW(
        PIPE_NAME,
        GENERIC_READ | GENERIC_WRITE,
        0,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if handle == INVALID_HANDLE_VALUE:
        return None
    return handle


def _send_message(handle, msg: dict) -> dict | None:
    """Send a JSON message and read the response."""
    data = json.dumps(msg).encode("utf-8")
    bytes_written = ctypes.wintypes.DWORD(0)
    ok = kernel32.WriteFile(handle, data, len(data), ctypes.byref(bytes_written), None)
    if not ok:
        return None

    # Read response
    buffer = ctypes.create_string_buffer(4096)
    bytes_read = ctypes.wintypes.DWORD(0)
    ok = kernel32.ReadFile(handle, buffer, 4095, ctypes.byref(bytes_read), None)
    if not ok:
        return None

    try:
        return json.loads(buffer.raw[: bytes_read.value].decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def is_daemon_running() -> bool:
    """Check if the toast daemon pipe exists."""
    handle = _connect_pipe()
    if handle is not None:
        kernel32.CloseHandle(handle)
        return True
    return False


def _start_daemon() -> bool:
    """Start the toast daemon process."""
    try:
        if getattr(sys, "frozen", False):
            # Frozen mode: re-launch the same exe with --toast-daemon
            subprocess.Popen(
                [sys.executable, "--toast-daemon"],
                creationflags=CREATE_NO_WINDOW,
            )
        else:
            # Development mode: use pythonw
            python_dir = os.path.dirname(sys.executable)
            pythonw = os.path.join(python_dir, "pythonw.exe")
            if not os.path.exists(pythonw):
                import shutil

                pythonw = shutil.which("pythonw.exe") or shutil.which("pythonw")
            if not pythonw or not os.path.exists(pythonw):
                pythonw = sys.executable

            subprocess.Popen(
                [pythonw, "-m", "agentbell.toast_daemon"],
                creationflags=CREATE_NO_WINDOW,
            )
        return True
    except Exception as e:
        logger.error("Failed to start toast daemon: %s", e)
        return False


def ensure_daemon() -> bool:
    """Ensure the toast daemon is running. Returns True if ready."""
    if is_daemon_running():
        return True

    # Start daemon
    if not _start_daemon():
        return False

    # Wait for daemon to be ready
    for _ in range(10):
        time.sleep(0.05)
        if is_daemon_running():
            return True

    return False


def send_toast(params: dict) -> bool:
    """Send a toast request to the daemon. Returns True on success."""
    if not ensure_daemon():
        return False

    # Try to connect with retries
    handle = None
    for _ in range(3):
        handle = _connect_pipe()
        if handle is not None:
            break
        time.sleep(0.05)

    if handle is None:
        return False

    try:
        # Add cmd: "show" to the request
        request = {"cmd": "show", **params}
        response = _send_message(handle, request)
        if response and response.get("ok"):
            return True
        else:
            logger.warning("Toast daemon rejected: %s", response)
            return False
    except Exception as e:
        logger.error("Pipe communication failed: %s", e)
        return False
    finally:
        kernel32.CloseHandle(handle)


def dismiss_toast(toast_id: str) -> bool:
    """Request dismissal of a specific toast."""
    if not is_daemon_running():
        return False

    handle = _connect_pipe()
    if handle is None:
        return False

    try:
        response = _send_message(handle, {"cmd": "dismiss", "id": toast_id})
        return response and response.get("ok")
    except Exception:
        return False
    finally:
        kernel32.CloseHandle(handle)
