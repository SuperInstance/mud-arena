"""Tests for the agent simulation (perceive → decide → act)."""

from mud_arena.agent import Agent
from mud_arena.commands import Command, Verb
from mud_arena.events import EventBus, EventType
from mud_arena.inventory import Item
from mud_arena.rooms import Room, RoomGraph


def _make_world() -> tuple[Agent, RoomGraph, EventBus]:
    g = RoomGraph()
    g.add_room(Room(
        id="start", name="Start Room", description="A quiet room.",
        items=["coin", "key"], npcs=["guard"],
    ))
    g.add_room(Room(id="next", name="Next Room", description="Another room."))
    g.connect("start", "next", "north", "south")
    agent = Agent(id="hero", current_room="start")
    bus = EventBus()
    return agent, g, bus


class TestAgentSimulation:
    def test_perceive_room(self) -> None:
        agent, graph, _ = _make_world()
        p = agent.perceive(graph)
        assert p["room_id"] == "start"
        assert p["room_name"] == "Start Room"
        assert "coin" in p["items"]
        assert "guard" in p["npcs"]

    def test_decide_returns_command(self) -> None:
        agent, graph, _ = _make_world()
        perception = agent.perceive(graph)
        cmd = agent.decide(perception)
        assert isinstance(cmd, Command)

    def test_act_move(self) -> None:
        agent, graph, bus = _make_world()
        result = agent.step(graph, bus, "go north")
        assert agent.current_room == "next"
        assert "Another room" in result

    def test_act_take_item(self) -> None:
        agent, graph, bus = _make_world()
        result = agent.step(graph, bus, "take coin")
        assert "pick up coin" in result
        assert agent.inventory.has("coin")
        room = graph.get("start")
        assert "coin" not in room.items

    def test_act_drop_item(self) -> None:
        agent, graph, bus = _make_world()
        agent.inventory.add(Item(name="gem"))
        result = agent.step(graph, bus, "drop gem")
        assert "drop gem" in result
        assert not agent.inventory.has("gem")
        assert "gem" in graph.get("start").items

    def test_act_use_item(self) -> None:
        agent, graph, bus = _make_world()
        agent.inventory.add(Item(name="potion", uses=2))
        result = agent.step(graph, bus, "use potion")
        assert "use potion" in result

    def test_act_talk_to_npc(self) -> None:
        agent, graph, bus = _make_world()
        result = agent.step(graph, bus, "talk to guard")
        assert "guard" in result

    def test_room_state_changes(self) -> None:
        """Taking an item removes it from the room."""
        agent, graph, bus = _make_world()
        agent.step(graph, bus, "take key")
        room = graph.get("start")
        assert "key" not in room.items

    def test_events_emitted_on_move(self) -> None:
        agent, graph, bus = _make_world()
        agent.step(graph, bus, "north")
        leaves = bus.history(EventType.ROOM_LEAVE)
        enters = bus.history(EventType.ROOM_ENTER)
        assert len(leaves) == 1
        assert len(enters) == 1
        assert enters[0].room == "next"

    def test_events_emitted_on_pickup(self) -> None:
        agent, graph, bus = _make_world()
        agent.step(graph, bus, "take coin")
        events = bus.history(EventType.ITEM_PICKED_UP)
        assert len(events) == 1
        assert events[0].data["item"] == "coin"
