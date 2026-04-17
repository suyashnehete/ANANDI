"""
Event Bus — In-process, typed event system with SQLite persistence.

All services communicate via events. Producers emit, consumers subscribe.
Every event is logged to an append-only SQLite table for replay/debugging.
"""

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable

IST = timezone(timedelta(hours=5, minutes=30))


# ── Event Types ─────────────────────────────────────────────────────────────

class EventType(str, Enum):
    # Input
    USER_MESSAGE = "user_message"
    CALENDAR_UPDATED = "calendar_updated"

    # Internal
    INTENT_CLASSIFIED = "intent_classified"
    CONTEXT_ASSEMBLED = "context_assembled"
    MEMORY_STORED = "memory_stored"
    MEMORY_RECALLED = "memory_recalled"

    # Action
    AGENT_RESPONSE = "agent_response"
    REMINDER_TRIGGERED = "reminder_triggered"
    ACTIVITY_LOGGED = "activity_logged"

    # System
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    SYSTEM_STATE_CHANGED = "system_state_changed"
    CONVERSATION_STORED = "conversation_stored"
    CONSOLIDATION_COMPLETED = "consolidation_completed"


@dataclass
class Event:
    type: EventType
    data: dict = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: str = field(default_factory=lambda: datetime.now(IST).isoformat())
    correlation_id: str | None = None
    source: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d


# ── Event Bus ───────────────────────────────────────────────────────────────

class EventBus:
    """
    In-process synchronous event bus.
    - Subscribe handlers to event types
    - Emit events (handlers called in registration order)
    - All events persisted to SQLite event_log
    """

    def __init__(self, db_path: str | None = None):
        self._subscribers: dict[EventType, list[Callable]] = {}
        self._lock = threading.Lock()
        self._db_path = db_path
        self._local = threading.local()
        if db_path:
            self._init_event_log()

    @property
    def _conn(self) -> sqlite3.Connection | None:
        if not self._db_path:
            return None
        if not hasattr(self._local, "connection"):
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            self._local.connection = conn
        return self._local.connection

    def _init_event_log(self):
        conn = self._conn
        if conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    source TEXT DEFAULT '',
                    correlation_id TEXT,
                    timestamp TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_event_log_type ON event_log(type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_event_log_timestamp ON event_log(timestamp)"
            )
            conn.commit()

    def subscribe(self, event_type: EventType, handler: Callable):
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable):
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    h for h in self._subscribers[event_type] if h is not handler
                ]

    def emit(self, event: Event):
        # Persist to event log
        self._persist_event(event)

        # Notify subscribers
        with self._lock:
            handlers = list(self._subscribers.get(event.type, []))
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"[EventBus] Handler error for {event.type.value}: {e}")

    def _persist_event(self, event: Event):
        conn = self._conn
        if not conn:
            return
        try:
            conn.execute(
                """INSERT INTO event_log
                   (event_id, type, data, source, correlation_id, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    event.event_id,
                    event.type.value,
                    json.dumps(event.data, default=str),
                    event.source,
                    event.correlation_id,
                    event.timestamp,
                ],
            )
            conn.commit()
        except Exception as e:
            # Log and re-raise — event log contract must be honoured
            print(f"[EventBus] CRITICAL persist error: {e}")
            raise

    def get_events(
        self,
        event_type: EventType | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        conn = self._conn
        if not conn:
            return []
        query = "SELECT * FROM event_log"
        params: list[Any] = []
        conditions = []
        if event_type:
            conditions.append("type = ?")
            params.append(event_type.value)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        safe_limit = min(max(int(limit), 1), 10000)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(safe_limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
