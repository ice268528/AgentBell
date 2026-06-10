"""Persistent Event Store for AgentBell.

JSON file-based storage at ~/.agentbell/events.json.
Thread-safe. Max 100 events. Supports add, get_recent, clear.
"""

import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Literal


@dataclass
class AgentBellEvent:
    """Single event record in the store."""
    id: str
    timestamp: float
    session_id: str = ""
    session_label: str = ""
    cwd: str = ""
    hook_event_name: str = ""
    notification_type: str = ""
    kind: Literal["permission_required", "waiting_input", "task_completed", "error", "info"] = "info"
    title: str = ""
    message: str = ""
    tool_name: str = ""
    command: str = ""
    project_path: str = ""
    raw_payload: dict = field(default_factory=dict)


MAX_EVENTS = 100


class EventStore:
    """Persistent event store backed by a JSON file."""

    def __init__(self, path: str | None = None):
        self._dir = os.path.join(os.path.expanduser("~"), ".agentbell")
        os.makedirs(self._dir, exist_ok=True)
        self._path = path or os.path.join(self._dir, "events.json")
        self._events: list[dict] = []
        self._lock = threading.RLock()
        self._load()

    def _load(self):
        """Load events from disk."""
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._events = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._events = []
        else:
            self._events = []

    def _save(self):
        """Persist events to disk (must hold lock)."""
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._events[-MAX_EVENTS:], f, ensure_ascii=False)
        except OSError:
            pass

    def add(self, event: AgentBellEvent):
        """Add an event, persist, and enforce max capacity."""
        with self._lock:
            self._events.append(asdict(event))
            if len(self._events) > MAX_EVENTS:
                self._events = self._events[-MAX_EVENTS:]
            self._save()

    def get_recent(self, n: int = 20) -> list[dict]:
        """Return the most recent n events, newest first."""
        with self._lock:
            return list(reversed(self._events[-n:]))

    def get_all(self) -> list[dict]:
        """Return all events, newest first."""
        with self._lock:
            return list(reversed(self._events))

    def count(self) -> int:
        with self._lock:
            return len(self._events)

    def clear(self):
        """Clear all events."""
        with self._lock:
            self._events = []
            self._save()

    def get_pending_permission_count(self) -> int:
        """Count events with kind=permission_required that are recent (last 60s)."""
        cutoff = time.time() - 60
        with self._lock:
            return sum(
                1 for e in self._events
                if e.get("kind") == "permission_required"
                and e.get("timestamp", 0) > cutoff
            )
