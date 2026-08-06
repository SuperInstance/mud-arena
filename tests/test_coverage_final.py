"""Coverage gap closure tests for mud_arena — targeting remaining uncovered lines.

Gaps:
- agent.py 50: __post_post__ when name is empty
- agent.py 128: perceive in void (no room)
- agent.py 156: _do_go invalid direction
- agent.py 163: _do_look in void
- agent.py 168: _do_take no target
- agent.py 184,186: _do_drop no target / not in inventory
- agent.py 201,203,205: _do_use edge cases
- agent.py 217: _do_talk no target
- agent.py 232: _do_examine no target
- agent.py 236: _do_inventory empty
- events.py 86-87: clear()
- inventory.py 35,37: add capacity exceeded
- inventory.py 100,102,111: use() edge cases
- rooms.py 85,90,105: navigate non-existent room
"""
import pytest

from mud_arena.agent import Agent
from mud_arena.commands import Command, Verb, parse_command
from mud_arena.events import EventBus, EventType, Event
from mud_arena.inventory import Item, Inventory
from mud_arena.rooms import Room, RoomGraph


# ── Agent edge cases ────────────────────────────────────────────────────────

class TestAgentVoidPerception:
    def test_perceive_void(self):
        """Agent in a non-existent room should perceive The Void."""
        agent = Agent(id="test", current_room="nonexistent")
        graph = RoomGraph()
        p = agent.perceive(graph)
        assert p["room_id"] == "nonexistent"
        assert p["room_name"] == "The Void"
        assert p["description"] == "You are nowhere."
        assert p["exits"] == {}
        assert p["items"] == []
        assert p["npcs"] == []


class TestAgentGoEdgeCases:
    def test_go_invalid_direction(self):
        """Going in an invalid direction should return can't message."""
        graph = RoomGraph()
        graph.add_room(Room(id="start", name="Start", description="A room."))
        agent = Agent(id="test", current_room="start")
        bus = EventBus()
        result = agent._do_go("up", graph, bus)
        assert "can't go up" in result

    def test_go_from_nonexistent_room(self):
        """Navigating from a room that doesn't exist returns None."""
        graph = RoomGraph()
        agent = Agent(id="test", current_room="ghost")
        bus = EventBus()
        result = agent._do_go("north", graph, bus)
        assert "can't go north" in result


class TestAgentLookEdgeCases:
    def test_look_in_void(self):
        """Looking around in a non-existent room."""
        graph = RoomGraph()
        agent = Agent(id="test", current_room="void")
        result = agent._do_look(graph)
        assert result == "You are in the void."


class TestAgentTakeEdgeCases:
    def test_take_no_target(self):
        """Take with no target."""
        graph = RoomGraph()
        graph.add_room(Room(id="start", name="Start", description="Room."))
        agent = Agent(id="test", current_room="start")
        bus = EventBus()
        result = agent._do_take("", graph, bus)
        assert "Take what" in result

    def test_take_from_void_room(self):
        """Take from a room that doesn't exist."""
        graph = RoomGraph()
        agent = Agent(id="test", current_room="ghost")
        bus = EventBus()
        result = agent._do_take("item", graph, bus)
        # Room is None so we should get a can't message or error
        assert result is not None


class TestAgentDropEdgeCases:
    def test_drop_no_target(self):
        """Drop with no target."""
        agent = Agent(id="test", current_room="start")
        graph = RoomGraph()
        graph.add_room(Room(id="start", name="Start", description="Room."))
        bus = EventBus()
        result = agent._do_drop("", graph, bus)
        assert "Drop what" in result

    def test_drop_not_in_inventory(self):
        """Drop an item not carried."""
        agent = Agent(id="test", current_room="start")
        graph = RoomGraph()
        graph.add_room(Room(id="start", name="Start", description="Room."))
        bus = EventBus()
        result = agent._do_drop("sword", graph, bus)
        assert "don't have" in result


class TestAgentUseEdgeCases:
    def test_use_no_target(self):
        agent = Agent(id="test", current_room="start")
        bus = EventBus()
        result = agent._do_use("", "", bus)
        assert "Use what" in result

    def test_use_not_in_inventory(self):
        agent = Agent(id="test", current_room="start")
        bus = EventBus()
        result = agent._do_use("potion", "", bus)
        assert "don't have" in result

    def test_use_non_usable_item(self):
        """Use an item that is not usable."""
        item = Item(name="rock", usable=False)
        agent = Agent(id="test", current_room="start")
        agent.inventory.add(item)
        bus = EventBus()
        result = agent._do_use("rock", "", bus)
        assert "can't use" in result


class TestAgentTalkEdgeCases:
    def test_talk_no_target(self):
        agent = Agent(id="test", current_room="start")
        graph = RoomGraph()
        result = agent._do_talk("", graph)
        assert "Talk to whom" in result

    def test_talk_to_nonexistent_npc(self):
        graph = RoomGraph()
        graph.add_room(Room(id="start", name="Start", description="Room."))
        agent = Agent(id="test", current_room="start")
        result = agent._do_talk("wizard", graph)
        assert "don't see wizard" in result


class TestAgentExamineEdgeCases:
    def test_examine_no_target(self):
        agent = Agent(id="test", current_room="start")
        graph = RoomGraph()
        result = agent._do_examine("", graph)
        assert "Examine what" in result

    def test_examine_not_found(self):
        agent = Agent(id="test", current_room="start")
        graph = RoomGraph()
        graph.add_room(Room(id="start", name="Start", description="Room."))
        result = agent._do_examine("nothing", graph)
        assert "don't see" in result

    def test_examine_item_in_inventory(self):
        """Examining an item in inventory should return its description."""
        agent = Agent(id="test", current_room="start")
        graph = RoomGraph()
        graph.add_room(Room(id="start", name="Start", description="Room."))
        item = Item(name="gem", description="A sparkling red gem.")
        agent.inventory.add(item)
        result = agent._do_examine("gem", graph)
        assert "sparkling red gem" in result


class TestAgentInventoryEmpty:
    def test_inventory_empty(self):
        agent = Agent(id="test", current_room="start")
        result = agent._do_inventory()
        assert "carrying nothing" in result

    def test_inventory_with_items(self):
        agent = Agent(id="test", current_room="start")
        agent.inventory.add(Item(name="sword"))
        agent.inventory.add(Item(name="shield"))
        result = agent._do_inventory()
        assert "sword" in result
        assert "shield" in result


class TestAgentNameDefault:
    def test_agent_default_name(self):
        """Agent with empty name gets id as name."""
        agent = Agent(id="hero", name="", current_room="start")
        assert agent.name == "hero"


class TestAgentSetDecisionFn:
    def test_set_decision_fn(self):
        """set_decision_fn should replace the decision function."""
        agent = Agent(id="test", current_room="start")
        custom_cmd = Command(verb=Verb.LOOK, raw="custom")
        agent.set_decision_fn(lambda p: custom_cmd)
        result = agent.decide({})
        assert result is custom_cmd


class TestAgentUnknownCommand:
    def test_act_unknown_verb(self):
        """Unknown verb should return error message."""
        agent = Agent(id="test", current_room="start")
        graph = RoomGraph()
        graph.add_room(Room(id="start", name="Start", description="Room."))
        bus = EventBus()
        cmd = Command(verb=Verb.QUIT, raw="fly away")  # QUIT returns goodbye, need truly unknown
        # Create a command with a verb that doesn't match any handler
        cmd = Command(verb=Verb.UNKNOWN, raw="dance")  # UNKNOWN verb hits fallback
        result = agent.act(cmd, graph, bus)
        assert "Unknown command" in result


class TestAgentLookWithItemsAndNpcs:
    def test_look_room_with_items_and_npcs(self):
        """Looking around should list items and NPCs."""
        graph = RoomGraph()
        graph.add_room(Room(
            id="market",
            name="Market",
            description="A busy market.",
            items=["apple", "coin"],
            npcs=["merchant", "guard"],
        ))
        agent = Agent(id="test", current_room="market")
        result = agent._do_look(graph)
        assert "[Market]" in result
        assert "apple" in result
        assert "coin" in result
        assert "merchant" in result
        assert "guard" in result
        assert "Exits:" not in result  # No exits defined


# ── EventBus.clear() (events.py 86-87) ──────────────────────────────────────

class TestEventBusClear:
    def test_clear_removes_handlers_and_log(self):
        bus = EventBus()
        bus.subscribe(EventType.ROOM_ENTER, lambda e: None)
        bus.emit(Event(
            type=EventType.ROOM_ENTER,
            source="test",
            data={},
            room="start",
        ))
        assert len(bus.history()) == 1
        bus.clear()
        assert len(bus.history()) == 0

    def test_clear_removes_all_handlers(self):
        bus = EventBus()
        called = []
        bus.subscribe(EventType.ITEM_PICKED_UP, lambda e: called.append(e))
        bus.clear()
        bus.emit(Event(
            type=EventType.ITEM_PICKED_UP,
            source="test",
            data={},
            room="start",
        ))
        assert len(called) == 0


# ── Inventory capacity (inventory.py 35,37) ──────────────────────────────────

class TestInventoryCapacity:
    def test_add_exceeds_capacity(self):
        inv = Inventory(capacity=2)
        assert inv.add(Item(name="item1")) is True
        assert inv.add(Item(name="item2")) is True
        assert inv.add(Item(name="item3")) is False
        assert len(inv) == 2

    def test_add_zero_capacity_means_unlimited(self):
        inv = Inventory(capacity=0)
        for i in range(100):
            assert inv.add(Item(name=f"item{i}")) is True


# ── Inventory.use() edge cases (inventory.py 100,102,111) ───────────────────

class TestInventoryUseEdgeCases:
    def test_use_nonexistent_item(self):
        inv = Inventory()
        assert inv.use("ghost") is False

    def test_use_non_usable_item(self):
        inv = Inventory()
        inv.add(Item(name="rock", usable=False))
        assert inv.use("rock") is False
        # Item should still be in inventory
        assert inv.has("rock")

    def test_use_item_with_zero_uses(self):
        """Item with uses=0 should fail to use."""
        item = Item(name="empty_bottle", usable=True, uses=0)
        assert item.use() is False

    def test_use_item_until_zero_uses(self):
        """Item with uses=1 should be auto-removed after use."""
        inv = Inventory()
        item = Item(name="potion", usable=True, uses=1)
        inv.add(item)
        assert inv.use("potion") is True
        # Should be auto-removed since uses dropped to 0
        assert not inv.has("potion")

    def test_use_item_multiple_uses(self):
        """Item with multiple uses should decrement."""
        inv = Inventory()
        item = Item(name="key", usable=True, uses=3)
        inv.add(item)
        assert inv.use("key") is True
        assert inv.use("key") is True
        assert inv.use("key") is True
        # All uses consumed, should be removed
        assert not inv.has("key")

    def test_contains_operator(self):
        """Test __contains__ via 'in' operator."""
        inv = Inventory()
        inv.add(Item(name="sword"))
        assert "sword" in inv
        assert "shield" not in inv


# ── Rooms edge cases (rooms.py 85,90,105) ───────────────────────────────────

class TestRoomsEdgeCases:
    def test_navigate_from_nonexistent_room(self):
        graph = RoomGraph()
        assert graph.navigate("ghost", "north") is None

    def test_navigate_no_exit(self):
        graph = RoomGraph()
        graph.add_room(Room(id="start", name="Start", description="A room."))
        assert graph.navigate("start", "up") is None

    def test_exits_for_nonexistent_room(self):
        graph = RoomGraph()
        assert graph.exits_for("ghost") == {}

    def test_exits_for_existing_room(self):
        graph = RoomGraph()
        graph.add_room(Room(id="start", name="Start", description="A room.", exits={"north": "hall"}))
        exits = graph.exits_for("start")
        assert exits == {"north": "hall"}

    def test_contains_check(self):
        graph = RoomGraph()
        graph.add_room(Room(id="start", name="Start", description="A room."))
        assert "start" in graph
        assert "ghost" not in graph

    def test_len_empty_graph(self):
        graph = RoomGraph()
        assert len(graph) == 0

    def test_all_rooms(self):
        graph = RoomGraph()
        graph.add_room(Room(id="a", name="A", description="Room A."))
        graph.add_room(Room(id="b", name="B", description="Room B."))
        rooms = graph.all_rooms()
        assert len(rooms) == 2
        assert graph.room_count() == 2
