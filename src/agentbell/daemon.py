"""AgentBell daemon - HTTP server for receiving Claude Code hook events.

Listens on 127.0.0.1:37371, accepts POST /hooks/claude with JSON payload.
Manages session state, event routing, toast display, and tray icon.
"""

import json
import os
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from dataclasses import dataclass, field
from typing import Any

from agentbell.logging_utils import setup_logging

logger = setup_logging()

DAEMON_HOST = "127.0.0.1"
DAEMON_PORT = 37371
DAEMON_URL = f"http://{DAEMON_HOST}:{DAEMON_PORT}"


# ── Session State Machine ────────────────────────────────────────────────────
SESSION_STATES = [
    "running",
    "waiting_permission",
    "waiting_input",
    "background_running",
    "task_completed",
    "error",
]


@dataclass
class SessionInfo:
    session_id: str = ""
    label: str = ""
    cwd: str = ""
    agent_id: str = ""
    agent_type: str = ""
    state: str = "running"
    last_event_type: str = ""
    last_event_time: float = 0.0
    pending_permission: bool = False
    raw_payload: dict = field(default_factory=dict)


class SessionRegistry:
    """Manages per-session state."""

    def __init__(self):
        self._sessions: dict[str, SessionInfo] = {}
        self._lock = threading.Lock()

    def get_or_create(self, session_id: str) -> SessionInfo:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionInfo(session_id=session_id)
            return self._sessions[session_id]

    def update(self, session_id: str, **kwargs) -> SessionInfo:
        with self._lock:
            s = self.get_or_create(session_id)
            for k, v in kwargs.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            return s

    def get_all(self) -> list[SessionInfo]:
        with self._lock:
            return list(self._sessions.values())

    def get_pending_permission_count(self) -> int:
        with self._lock:
            return sum(1 for s in self._sessions.values() if s.pending_permission)

    def get_pending_permission_sessions(self) -> list[SessionInfo]:
        with self._lock:
            return [s for s in self._sessions.values() if s.pending_permission]


def resolve_session_label(payload: dict, session_id: str) -> str:
    """Resolve session label from payload, priority order:
    1. session_title
    2. cwd directory name
    3. session_id[:6]
    """
    if payload.get("session_title"):
        return payload["session_title"]
    cwd = payload.get("cwd", "")
    if cwd:
        return os.path.basename(cwd.rstrip("/\\"))
    if session_id:
        return f"session {session_id[:6]}"
    return "unknown"


# ── Event Router ─────────────────────────────────────────────────────────────
class EventRouter:
    """Routes events, dedup, decide toast display."""

    def __init__(self, registry: SessionRegistry):
        self.registry = registry
        self._recent_events: dict[str, float] = {}
        self._lock = threading.Lock()
        self._toast_callback = None  # set by daemon

    def set_toast_callback(self, callback):
        self._toast_callback = callback

    def _dedup_key(self, session_id: str, event_type: str, extra: str = "") -> str:
        return f"{session_id}:{event_type}:{extra}"

    def _is_duplicate(self, key: str, window_sec: float = 3.0) -> bool:
        now = time.time()
        with self._lock:
            last = self._recent_events.get(key, 0)
            if now - last < window_sec:
                return True
            self._recent_events[key] = now
            return False

    def _cleanup_old_events(self):
        now = time.time()
        with self._lock:
            self._recent_events = {
                k: v for k, v in self._recent_events.items()
                if now - v < 30
            }

    def route(self, event_name: str, payload: dict) -> dict:
        """Route an event. Returns {action, toast_type, suppressed_reason}."""
        session_id = payload.get("session_id", "default")
        notification_type = payload.get("notification_type", "")
        tool_use_id = payload.get("tool_use_id", "")
        task_id = payload.get("task_id", "")

        # Update session
        label = resolve_session_label(payload, session_id)
        self.registry.update(session_id,
            label=label,
            cwd=payload.get("cwd", ""),
            agent_id=payload.get("agent_id", ""),
            agent_type=payload.get("agent_type", ""),
            last_event_type=event_name,
            last_event_time=time.time(),
            raw_payload=payload,
        )

        result = {"action": "none", "toast_type": None, "suppressed_reason": None}

        # ── PermissionRequest ──
        if event_name == "PermissionRequest":
            dedup_key = self._dedup_key(session_id, "permission", tool_use_id)
            if self._is_duplicate(dedup_key):
                result["suppressed_reason"] = "duplicate_event"
                return result
            self.registry.update(session_id, state="waiting_permission", pending_permission=True)
            result["action"] = "toast"
            result["toast_type"] = "permission_required"
            return result

        # ── Notification ──
        if event_name == "Notification":
            if notification_type == "permission_prompt":
                dedup_key = self._dedup_key(session_id, "permission", tool_use_id)
                if self._is_duplicate(dedup_key):
                    result["suppressed_reason"] = "duplicate_event"
                    return result
                self.registry.update(session_id, state="waiting_permission", pending_permission=True)
                result["action"] = "toast"
                result["toast_type"] = "permission_required"
                return result
            elif notification_type == "idle_prompt":
                dedup_key = self._dedup_key(session_id, "idle")
                if self._is_duplicate(dedup_key):
                    result["suppressed_reason"] = "duplicate_event"
                    return result
                self.registry.update(session_id, state="waiting_input", pending_permission=False)
                result["action"] = "toast"
                result["toast_type"] = "waiting_input"
                return result
            else:
                result["suppressed_reason"] = "notification_type_not_enabled"
                return result

        # ── Stop ──
        if event_name == "Stop":
            bg_tasks = payload.get("background_tasks", [])
            if bg_tasks:
                self.registry.update(session_id, state="background_running")
                result["suppressed_reason"] = "stop_has_background_tasks"
            else:
                self.registry.update(session_id, state="waiting_input", pending_permission=False)
                result["suppressed_reason"] = "stop_is_not_task_done"
            return result

        # ── TaskCompleted ──
        if event_name == "TaskCompleted":
            task_subject = payload.get("task_subject", "")
            if not task_subject:
                result["suppressed_reason"] = "no_task_subject"
                return result
            dedup_key = self._dedup_key(session_id, "task_completed", task_id)
            if self._is_duplicate(dedup_key):
                result["suppressed_reason"] = "duplicate_event"
                return result
            self.registry.update(session_id, state="task_completed", pending_permission=False)
            result["action"] = "toast"
            result["toast_type"] = "task_done"
            return result

        # ── PreToolUse / PostToolUse / others ──
        if event_name in ("PreToolUse", "PostToolUse"):
            result["suppressed_reason"] = "pre_or_post_tool_use_not_permission"
            return result

        result["suppressed_reason"] = f"event_type_{event_name}_not_handled"
        return result


# ── Event Logger ─────────────────────────────────────────────────────────────
class EventLogger:
    """Logs events to hook-events.jsonl."""

    def __init__(self):
        self._log_dir = os.path.join(os.path.expanduser("~"), ".agentbell", "logs")
        os.makedirs(self._log_dir, exist_ok=True)
        self._log_path = os.path.join(self._log_dir, "hook-events.jsonl")

    def log(self, event_name: str, payload: dict, route_result: dict,
            session_id: str, session_label: str):
        import json as _json
        record = {
            "timestamp": time.time(),
            "session_id": session_id,
            "session_label": session_label,
            "cwd": payload.get("cwd", ""),
            "hook_event_name": event_name,
            "notification_type": payload.get("notification_type", ""),
            "agent_id": payload.get("agent_id", ""),
            "agent_type": payload.get("agent_type", ""),
            "normalized_state": route_result.get("action", ""),
            "emitted_toast_type": route_result.get("toast_type", ""),
            "suppressed_reason": route_result.get("suppressed_reason", ""),
            "raw_payload": payload,
        }
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(_json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass


# ── HTTP Handler ─────────────────────────────────────────────────────────────
class HookHandler(BaseHTTPRequestHandler):
    """Handles POST /hooks/claude from Claude Code hooks."""

    daemon = None  # set by DaemonServer

    def do_POST(self):
        if self.path == "/hooks/claude":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                payload = {}

            # Extract event name from payload
            event_name = payload.get("hook_event_name", "")
            if not event_name:
                # Try to infer from hook_type
                hook_type = payload.get("hook_type", "")
                event_name = hook_type

            # Process in background thread to not block Claude Code
            if self.daemon:
                threading.Thread(
                    target=self.daemon.process_event,
                    args=(event_name, payload),
                    daemon=True,
                ).start()

            # Return immediately
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default HTTP logging
        pass


# ── Daemon Server ────────────────────────────────────────────────────────────
class DaemonServer:
    """Main daemon that manages sessions, routes events, shows toasts."""

    def __init__(self):
        self.registry = SessionRegistry()
        self.router = EventRouter(self.registry)
        self.event_logger = EventLogger()
        self._muted_until = 0.0
        self._toast_callback = None
        self._tray_callback = None
        self._setup_default_toast_callback()

    def set_toast_callback(self, callback):
        self._toast_callback = callback
        self.router.set_toast_callback(callback)

    def _setup_default_toast_callback(self):
        """Set up default toast callback that shows toasts."""
        from agentbell.toast_renderer import show_toast
        from agentbell.theme import ClaudeHookToastEvent
        import uuid

        def _default_toast_callback(toast_type, title, message, session_label="", session_id="", **kwargs):
            event = ClaudeHookToastEvent(
                id=uuid.uuid4().hex[:12],
                type=toast_type,
                title=title,
                message=message,
            )
            show_toast(event, session_label=session_label)

        self.set_toast_callback(_default_toast_callback)

    def set_tray_callback(self, callback):
        self._tray_callback = callback

    def process_event(self, event_name: str, payload: dict):
        """Process a hook event."""
        session_id = payload.get("session_id", "default")
        session_label = resolve_session_label(payload, session_id)

        # Route the event
        result = self.router.route(event_name, payload)

        # Log the event
        self.event_logger.log(event_name, payload, result, session_id, session_label)

        # Check if muted
        if time.time() < self._muted_until:
            result["suppressed_reason"] = "muted"
            return

        # Show toast if needed
        if result["action"] == "toast" and self._toast_callback:
            toast_type = result["toast_type"]
            # Check for aggregation
            pending = self.registry.get_pending_permission_sessions()
            if toast_type == "permission_required" and len(pending) > 1:
                # Aggregate
                labels = [s.label for s in pending]
                self._toast_callback(
                    toast_type="permission_aggregate",
                    title=f"{len(pending)} 个 Claude Code 会话等待授权",
                    message="、".join(labels[:3]) + ("..." if len(labels) > 3 else ""),
                    session_label=session_label,
                    session_count=len(pending),
                )
            else:
                self._toast_callback(
                    toast_type=toast_type,
                    title=payload.get("title"),
                    message=payload.get("message"),
                    session_label=session_label,
                    session_id=session_id,
                )

        # Update tray badge
        if self._tray_callback:
            self._tray_callback()

    def mute(self, minutes: int = 30):
        self._muted_until = time.time() + minutes * 60
        logger.info("Muted for %d minutes", minutes)

    def is_muted(self) -> bool:
        return time.time() < self._muted_until

    def start(self):
        """Start the daemon server."""
        server = HTTPServer((DAEMON_HOST, DAEMON_PORT), HookHandler)
        HookHandler.daemon = self
        logger.info("AgentBell daemon listening on %s:%d", DAEMON_HOST, DAEMON_PORT)
        server.serve_forever()


# ── Standalone daemon entry ──────────────────────────────────────────────────
def run_daemon():
    """Run the daemon standalone (blocking)."""
    daemon = DaemonServer()
    daemon.start()


def is_daemon_running() -> bool:
    """Check if daemon is already running."""
    import urllib.request
    try:
        req = urllib.request.Request(f"{DAEMON_URL}/health", method="GET")
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def send_to_daemon(event_name: str, payload: dict) -> bool:
    """Send event to daemon via HTTP."""
    import urllib.request
    data = json.dumps({
        "hook_event_name": event_name,
        **payload,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{DAEMON_URL}/hooks/claude",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception as e:
        logger.error("Failed to send to daemon: %s", e)
        return False
