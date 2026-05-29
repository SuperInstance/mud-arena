"""Tests for the room graph."""

from mud_arena.rooms import Room, RoomGraph


def _make_graph() -> RoomGraph:
    """Build a small three-room graph for testing."""
    g = RoomGraph()
    g.add_room(Room(id="lobby", name="Lobby", description="A grand lobby."))
    g.add_room(Room(id="hall", name="Great Hall", description="A vast hall with torches."))
    g.add_room(Room(id="cellar", name="Cellar", description="Dank and dark."))
    g.connect("lobby", "hall", "north", "south")
    g.connect("hall", "cellar", "down", "up")
    return g


class TestRoomGraph:
    def test_add_room(self) -> None:
        g = RoomGraph()
        g.add_room(Room(id="start", name="Start"))
        assert "start" in g
        assert g.room_count() == 1

    def test_navigate_between_rooms(self) -> None:
        g = _make_graph()
        assert g.navigate("lobby", "north") == "hall"
        assert g.navigate("hall", "south") == "lobby"
        assert g.navigate("hall", "down") == "cellar"

    def test_invalid_direction(self) -> None:
        g = _make_graph()
        assert g.navigate("lobby", "up") is None

    def test_current_room_tracking(self) -> None:
        g = _make_graph()
        # Simulate agent movement
        cur = "lobby"
        dest = g.navigate(cur, "north")
        assert dest == "hall"
        cur = dest
        assert cur == "hall"

    def test_remove_room_cleans_exits(self) -> None:
        g = _make_graph()
        g.remove_room("hall")
        assert g.navigate("lobby", "north") is None
        assert g.navigate("cellar", "up") is None

    def test_exits_for(self) -> None:
        g = _make_graph()
        exits = g.exits_for("lobby")
        assert exits == {"north": "hall"}

    def test_get_nonexistent(self) -> None:
        g = RoomGraph()
        assert g.get("nope") is None
