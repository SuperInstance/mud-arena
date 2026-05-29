"""Room graph — the spatial substrate of a MUD world."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Room:
    """A single room in the MUD world.

    Attributes:
        id: Unique room identifier.
        name: Human-readable room name.
        description: Flavor text shown on ``look``.
        exits: Mapping of direction name → destination room id.
        items: Items currently lying on the ground in this room.
        npcs: NPC names present in this room.
        metadata: Arbitrary extra data (tags, lighting, hazards, …).
    """

    id: str
    name: str = "An empty room"
    description: str = "You see nothing special."
    exits: Dict[str, str] = field(default_factory=dict)
    items: List[str] = field(default_factory=list)
    npcs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class RoomGraph:
    """A collection of interconnected rooms forming the MUD map.

    Supports adding rooms, linking exits, resolving navigation, and
    querying neighbours.
    """

    def __init__(self) -> None:
        self._rooms: Dict[str, Room] = {}

    # --- mutation -----------------------------------------------------------

    def add_room(self, room: Room) -> None:
        """Register a room.  Overwrites if a room with the same id exists."""
        self._rooms[room.id] = room

    def connect(self, room_a: str, room_b: str, direction: str, reverse: str = "") -> None:
        """Create a one-way (or two-way) exit between two rooms.

        Args:
            room_a: Source room id.
            room_b: Destination room id.
            direction: Direction label from *room_a* to *room_b*.
            reverse: If given, also create an exit from *room_b* back to
                     *room_a* with this label.
        """
        if room_a in self._rooms:
            self._rooms[room_a].exits[direction] = room_b
        if reverse and room_b in self._rooms:
            self._rooms[room_b].exits[reverse] = room_a

    def remove_room(self, room_id: str) -> None:
        """Remove a room and any exits pointing to it."""
        self._rooms.pop(room_id, None)
        for room in self._rooms.values():
            to_remove = [d for d, dest in room.exits.items() if dest == room_id]
            for d in to_remove:
                del room.exits[d]

    # --- queries ------------------------------------------------------------

    def get(self, room_id: str) -> Optional[Room]:
        """Look up a room by id; returns ``None`` if not found."""
        return self._rooms.get(room_id)

    def navigate(self, from_room: str, direction: str) -> Optional[str]:
        """Resolve a movement direction from a given room.

        Returns:
            The destination room id, or ``None`` if no exit exists.
        """
        room = self._rooms.get(from_room)
        if room is None:
            return None
        return room.exits.get(direction)

    def all_rooms(self) -> List[Room]:
        """Return all rooms in the graph."""
        return list(self._rooms.values())

    def room_count(self) -> int:
        """Number of rooms in the graph."""
        return len(self._rooms)

    def exits_for(self, room_id: str) -> Dict[str, str]:
        """Return the exits dict for a room (empty if not found)."""
        room = self._rooms.get(room_id)
        return dict(room.exits) if room else {}

    def __contains__(self, room_id: str) -> bool:
        return room_id in self._rooms

    def __len__(self) -> int:
        return len(self._rooms)
