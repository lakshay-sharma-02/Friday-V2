"""Event bus for MCU Friday.

Pub/sub system that connects all layers. Not just log-file-only —
real events that drive learning, prediction, and proactive behavior.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("friday_mcu.events")


class EventType(str, Enum):
    """All event types in the system."""

    # Primitive lifecycle
    PRIMITIVE_CALL = "primitive.call"
    PRIMITIVE_RESULT = "primitive.result"
    PRIMITIVE_ERROR = "primitive.error"

    # Step lifecycle
    STEP_START = "step.start"
    STEP_COMPLETE = "step.complete"
    STEP_FAILED = "step.failed"
    STEP_RETRY = "step.retry"

    # Goal lifecycle
    GOAL_START = "goal.start"
    GOAL_COMPLETE = "goal.complete"
    GOAL_FAILED = "goal.failed"
    GOAL_PLANNED = "goal.planned"

    # Learning
    PATTERN_DETECTED = "pattern.detected"
    MEMORY_STORED = "memory.stored"
    MEMORY_RECALLED = "memory.recalled"
    LEARNING_APPLIED = "learning.applied"

    # Observer
    USER_ACTION = "user.action"
    ANOMALY_DETECTED = "anomaly.detected"
    PREDICTION_MADE = "prediction.made"
    PREDICTION_CORRECT = "prediction.correct"
    PREDICTION_WRONG = "prediction.wrong"

    # Communication
    MESSAGE_SENT = "message.sent"
    MESSAGE_RECEIVED = "message.received"
    PROACTIVE_SUGGESTION = "proactive.suggestion"

    # System
    ADAPTER_CONNECTED = "adapter.connected"
    ADAPTER_DISCONNECTED = "adapter.disconnected"
    SYSTEM_HEALTH = "system.health"


@dataclass
class Event:
    """A single event in the system."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    type: EventType = EventType.SYSTEM_HEALTH
    source: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None  # tie events to a goal/step

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "type": self.type.value,
            "source": self.source,
            "data": self.data,
            "correlation_id": self.correlation_id,
        }


# Subscriber callback type
Subscriber = Callable[[Event], None]


class EventBus:
    """Pub/sub event bus. All layers publish and subscribe here.

    Usage:
        bus = EventBus()
        bus.subscribe(EventType.GOAL_COMPLETE, my_handler)
        bus.emit(Event(type=EventType.GOAL_COMPLETE, source="executor", data={...}))
    """

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[Subscriber]] = defaultdict(list)
        self._global_subscribers: list[Subscriber] = []
        self._history: list[Event] = []
        self._max_history = 10000
        self._lock = threading.RLock()

    def subscribe(
        self,
        event_type: EventType | None,
        callback: Subscriber,
    ) -> None:
        """Subscribe to a specific event type, or all events if None."""
        with self._lock:
            if event_type is None:
                self._global_subscribers.append(callback)
            else:
                self._subscribers[event_type].append(callback)

    def unsubscribe(
        self,
        event_type: EventType | None,
        callback: Subscriber,
    ) -> None:
        """Remove a subscription."""
        with self._lock:
            if event_type is None:
                self._global_subscribers = [
                    cb for cb in self._global_subscribers if cb != callback
                ]
            else:
                self._subscribers[event_type] = [
                    cb for cb in self._subscribers[event_type] if cb != callback
                ]

    def emit(self, event: Event) -> None:
        """Publish an event to all matching subscribers.

        Thread-safe: subscriber lists are snapshotted under the lock and
        invoked after it is released, so a subscriber that itself emits (or
        blocks) can never deadlock the bus. Subscriber errors are logged, not
        silently swallowed.
        """
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            type_subs = list(self._subscribers.get(event.type, []))
            global_subs = list(self._global_subscribers)

        for callback in type_subs + global_subs:
            try:
                callback(event)
            except Exception as exc:
                # Subscriber errors must never crash the bus, but they also
                # must not vanish silently — a dead WebSocket forwarder or
                # broken learning hook is a real bug worth hearing about.
                logger.warning(
                    "event subscriber error for %s: %s: %s",
                    event.type.value, type(exc).__name__, exc,
                )

    def recent(self, event_type: EventType | None = None, limit: int = 50) -> list[Event]:
        """Get recent events, optionally filtered by type."""
        with self._lock:
            if event_type is None:
                return list(self._history[-limit:])
            return [e for e in self._history if e.type == event_type][-limit:]

    def clear_history(self) -> None:
        """Clear event history."""
        with self._lock:
            self._history.clear()


# Global bus instance — import and use anywhere
_bus = EventBus()


def get_bus() -> EventBus:
    """Get the global event bus."""
    return _bus


def emit(
    event_type: EventType,
    source: str = "",
    data: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> Event:
    """Convenience: emit an event on the global bus."""
    event = Event(
        type=event_type,
        source=source,
        data=data or {},
        correlation_id=correlation_id,
    )
    _bus.emit(event)
    return event
