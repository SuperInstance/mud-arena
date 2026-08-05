"""
Integration tests for the MUD Arena.

Tests the full perceive → decide → act cycle across multiple subsystems.
"""

import pytest

from mud_arena.agent import Agent, _default_decide
from mud_arena.commands import Command, Verb, parse_command
from mud_arena.events import EventBus, EventType
from mud_arena.inventory import Inventory, Item
from mud_arena.rooms import Room, RoomGraph


@pytest.fixture
def small_world():
    """A small 3-room world with items and NPCs."""
    graph = RoomGraph()
    graph.add_room(Room(id="start", name="Starting Room", description="A dusty room."))
    graph.add_room(Room(id="hall", name="Great Hall", description="A grand hall with stone columns."))
    graph.add_room(Room(id="treasure", name="Treasure Chamber", description="Gold glints in the corner."))

    # Connect rooms
    graph.connect("start", "hall", "north", "south")
    graph.connect("hall", "treasure", "east", "west")

    # Add items and NPCs
    graph.get("start").items.append("torch")
    graph.get("treasure").items.append("gold_coin")
    graph.get("hall").npcs.append("sage")

    bus = EventBus()
    return graph, bus


@pytest.fixture
def agent_in_world(small_world):
    """An agent placed in the starting room of small_world."""
    graph, bus = small_world
    agent = Agent(id="hero", name="Hero", current_room="start")
    return agent, graph, bus


class TestAgentNavigation:
    """Test agent movement through the world."""

    def test_agent_starts_in_room(self, agent_in_world):
        agent, graph, bus = agent_in_world
        assert agent.current_room == "start"

    def test_go_north(self, agent_in_world):
        agent, graph, bus = agent_in_world
        result = agent.step(graph, bus, "go north")
        assert agent.current_room == "hall"
        assert "grand hall" in result.lower()

    def test_go_invalid_direction(self, agent_in_world):
        agent, graph, bus = agent_in_world
        result = agent.step(graph, bus, "go up")
        assert "can't go up" in result.lower()
        assert agent.current_room == "start"

    def test_navigate_two_rooms(self, agent_in_world):
        agent, graph, bus = agent_in_world
        agent.step(graph, bus, "go north")
        agent.step(graph, bus, "go east")
        assert agent.current_room == "treasure"

    def test_navigate_back(self, agent_in_world):
        agent, graph, bus = agent_in_world
        agent.step(graph, bus, "go north")
        agent.step(graph, bus, "go south")
        assert agent.current_room == "start"

    def test_movement_emits_events(self, agent_in_world):
        agent, graph, bus = agent_in_world
        agent.step(graph, bus, "go north")

        history = bus.history()
        types = [e.type for e in history]
        assert EventType.ROOM_LEAVE in types
        assert EventType.ROOM_ENTER in types

        leave_event = next(e for e in history if e.type == EventType.ROOM_LEAVE)
        assert leave_event.data["from"] == "start"
        assert leave_event.data["to"] == "hall"


class TestAgentInteraction:
    """Test agent interacting with items and NPCs."""

    def test_take_item(self, agent_in_world):
        agent, graph, bus = agent_in_world
        result = agent.step(graph, bus, "take torch")
        assert "pick up" in result.lower()
        assert agent.inventory.has("torch")
        assert "torch" not in graph.get("start").items

    def test_take_nonexistent(self, agent_in_world):
        agent, graph, bus = agent_in_world
        result = agent.step(graph, bus, "take sword")
        assert "don't see sword" in result.lower()

    def test_take_and_drop(self, agent_in_world):
        agent, graph, bus = agent_in_world
        agent.step(graph, bus, "take torch")
        result = agent.step(graph, bus, "drop torch")
        assert "drop" in result.lower()
        assert not agent.inventory.has("torch")
        assert "torch" in graph.get("start").items

    def test_examine_room_item(self, agent_in_world):
        agent, graph, bus = agent_in_world
        result = agent.step(graph, bus, "examine torch")
        assert "torch" in result.lower()

    def test_examine_nonexistent(self, agent_in_world):
        agent, graph, bus = agent_in_world
        result = agent.step(graph, bus, "examine dragon")
        assert "don't see" in result.lower()

    def test_talk_to_npc(self, agent_in_world):
        agent, graph, bus = agent_in_world
        agent.step(graph, bus, "go north")
        result = agent.step(graph, bus, "talk to sage")
        assert "sage" in result.lower()

    def test_talk_to_nonexistent(self, agent_in_world):
        agent, graph, bus = agent_in_world
        result = agent.step(graph, bus, "talk to dragon")
        assert "don't see dragon" in result.lower()


class TestAgentPerception:
    """Test the agent's perception system."""

    def test_perceive_shows_exits(self, agent_in_world):
        agent, graph, bus = agent_in_world
        perception = agent.perceive(graph)
        assert "north" in perception["exits"]

    def test_perceive_shows_items(self, agent_in_world):
        agent, graph, bus = agent_in_world
        perception = agent.perceive(graph)
        assert "torch" in perception["items"]

    def test_perceive_shows_npcs_after_move(self, agent_in_world):
        agent, graph, bus = agent_in_world
        agent.step(graph, bus, "go north")
        perception = agent.perceive(graph)
        assert "sage" in perception["npcs"]

    def test_perceive_in_void(self):
        """Agent perceives the void when in nonexistent room."""
        agent = Agent(id="lost", current_room="nowhere")
        graph = RoomGraph()
        perception = agent.perceive(graph)
        assert perception["room_name"] == "The Void"
        assert perception["exits"] == {}

    def test_look_shows_room_details(self, agent_in_world):
        agent, graph, bus = agent_in_world
        result = agent.step(graph, bus, "look")
        assert "Starting Room" in result
        assert "torch" in result
        assert "north" in result


class TestAgentInventory:
    """Test agent inventory management."""

    def test_inventory_empty_by_default(self, agent_in_world):
        agent, graph, bus = agent_in_world
        result = agent.step(graph, bus, "inventory")
        assert "carrying nothing" in result.lower()

    def test_inventory_after_take(self, agent_in_world):
        agent, graph, bus = agent_in_world
        agent.step(graph, bus, "take torch")
        result = agent.step(graph, bus, "inventory")
        assert "torch" in result.lower()

    def test_use_item(self, agent_in_world):
        agent, graph, bus = agent_in_world
        agent.step(graph, bus, "take torch")
        result = agent.step(graph, bus, "use torch")
        assert "use" in result.lower()


class TestFullSimulation:
    """End-to-end simulation scenarios."""

    def test_treasure_hunt(self, agent_in_world):
        """
        Full adventure: navigate to treasure room, pick up gold, return.
        """
        agent, graph, bus = agent_in_world

        # Navigate to treasure room
        agent.step(graph, bus, "go north")
        agent.step(graph, bus, "go east")
        assert agent.current_room == "treasure"

        # Take the treasure
        result = agent.step(graph, bus, "take gold_coin")
        assert "pick up" in result.lower()
        assert agent.inventory.has("gold_coin")

        # Return to start
        agent.step(graph, bus, "go west")
        agent.step(graph, bus, "go south")
        assert agent.current_room == "start"

        # Drop the treasure
        result = agent.step(graph, bus, "drop gold_coin")
        assert "drop" in result.lower()
        assert "gold_coin" in graph.get("start").items

    def test_event_log_complete(self, agent_in_world):
        """Verify the event bus captures the full adventure."""
        agent, graph, bus = agent_in_world

        agent.step(graph, bus, "take torch")
        agent.step(graph, bus, "go north")

        history = bus.history()
        # Should have: item_pickup + room_leave + room_enter
        types = [e.type for e in history]
        assert EventType.ITEM_PICKED_UP in types
        assert EventType.ROOM_LEAVE in types
        assert EventType.ROOM_ENTER in types

    def test_custom_decision_fn(self, small_world):
        """Test pluggable decision function."""
        graph, bus = small_world

        move_count = {"n": 0}

        def always_go_north(perception):
            exits = perception.get("exits", {})
            if "north" in exits:
                move_count["n"] += 1
                return Command(verb=Verb.GO, target="north")
            return Command(verb=Verb.LOOK)

        agent = Agent(
            id="explorer",
            current_room="start",
            _decision_fn=always_go_north,
        )

        result = agent.step(graph, bus)
        assert agent.current_room == "hall"
        assert move_count["n"] == 1

    def test_help_command(self, agent_in_world):
        agent, graph, bus = agent_in_world
        result = agent.step(graph, bus, "help")
        assert "go" in result.lower()
        assert "look" in result.lower()
        assert "take" in result.lower()

    def test_quit_command(self, agent_in_world):
        agent, graph, bus = agent_in_world
        result = agent.step(graph, bus, "quit")
        assert "goodbye" in result.lower()
