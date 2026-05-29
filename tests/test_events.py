"""Tests for the event system."""

from mud_arena.events import Event, EventBus, EventType


class TestEventSystem:
    def test_subscribe_and_emit(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        bus.subscribe(EventType.ROOM_ENTER, received.append)
        e = Event(type=EventType.ROOM_ENTER, source="agent1", room="lobby")
        bus.emit(e)
        assert len(received) == 1
        assert received[0].source == "agent1"

    def test_unsubscribe(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        handler = received.append
        bus.subscribe(EventType.ITEM_USED, handler)
        bus.unsubscribe(EventType.ITEM_USED, handler)
        bus.emit(Event(type=EventType.ITEM_USED))
        assert len(received) == 0

    def test_history_filter_by_type(self) -> None:
        bus = EventBus()
        bus.emit(Event(type=EventType.ROOM_ENTER, room="a"))
        bus.emit(Event(type=EventType.ROOM_LEAVE, room="a"))
        bus.emit(Event(type=EventType.ROOM_ENTER, room="b"))
        assert len(bus.history(EventType.ROOM_ENTER)) == 2

    def test_history_filter_by_room(self) -> None:
        bus = EventBus()
        bus.emit(Event(type=EventType.ROOM_ENTER, room="lobby"))
        bus.emit(Event(type=EventType.ROOM_ENTER, room="cellar"))
        assert len(bus.history(room="lobby")) == 1

    def test_room_event_triggers_reaction(self) -> None:
        """A room event fires and an agent reaction callback is invoked."""
        bus = EventBus()
        reactions: list[str] = []

        def on_room_event(event: Event) -> None:
            reactions.append(f"{event.source}:{event.data.get('msg', '')}")

        bus.subscribe(EventType.ROOM_EVENT, on_room_event)
        bus.emit(Event(
            type=EventType.ROOM_EVENT,
            source="trap_door",
            data={"msg": "click"},
            room="dungeon",
        ))
        assert reactions == ["trap_door:click"]
