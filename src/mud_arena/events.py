"""Event system — room events, agent reactions, and pub/sub dispatch."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List


class EventType(Enum):
    """Broad categories of events in the MUD world."""

    ROOM_ENTER = auto()
    ROOM_LEAVE = auto()
    ITEM_PICKED_UP = auto()
    ITEM_DROPPED = auto()
    ITEM_USED = auto()
    NPC_SPOKE = auto()
    ROOM_EVENT = auto()
    AGENT_ACTION = auto()
    CUSTOM = auto()


@dataclass
class Event:
    """An event that occurred in the MUD world.

    Attributes:
        type: The event category.
        source: Who or what caused the event (agent id, room id, …).
        data: Arbitrary payload.
        room: The room where the event occurred (if applicable).
    """

    type: EventType
    source: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    room: str = ""


# Type alias for event handler callbacks.
EventHandler = Callable[[Event], None]


class EventBus:
    """Simple synchronous pub/sub event bus.

    Agents and game systems subscribe to event types and receive
    notifications when matching events are emitted.
    """

    def __init__(self) -> None:
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._log: List[Event] = []

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for a specific event type."""
        self._handlers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove a previously registered handler."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit(self, event: Event) -> None:
        """Broadcast an event to all subscribed handlers.

        Also appends the event to an internal log.
        """
        self._log.append(event)
        for handler in self._handlers.get(event.type, []):
            handler(event)

    def history(self, event_type: EventType | None = None, room: str = "") -> List[Event]:
        """Return logged events, optionally filtered by type and/or room."""
        results = self._log
        if event_type is not None:
            results = [e for e in results if e.type == event_type]
        if room:
            results = [e for e in results if e.room == room]
        return list(results)

    def clear(self) -> None:
        """Clear all handlers and the event log."""
        self._handlers.clear()
        self._log.clear()
