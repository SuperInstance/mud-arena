"""Agent — a simulated entity that perceives and acts within the MUD world."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from mud_arena.commands import Command, Verb, parse_command
from mud_arena.events import Event, EventBus, EventType
from mud_arena.inventory import Inventory
from mud_arena.rooms import Room, RoomGraph


# Type alias: a decision function receives perception data and returns a Command.
DecisionFn = Callable[[Dict[str, Any]], Command]


def _default_decide(perception: Dict[str, Any]) -> Command:
    """Trivial decision function: just look around."""
    return Command(verb=Verb.LOOK, raw="look")


@dataclass
class Agent:
    """A simulated agent that inhabits the MUD world.

    The agent perceives its current room, decides on an action via a
    pluggable decision function, and executes the action — mutating room
    state and emitting events.

    Attributes:
        id: Unique agent identifier.
        name: Display name.
        current_room: Id of the room the agent currently occupies.
        inventory: The agent's personal inventory.
    """

    id: str
    name: str = ""
    current_room: str = ""
    inventory: Inventory = field(default_factory=Inventory)
    _decision_fn: DecisionFn = field(default=_default_decide, repr=False)

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.id

    def set_decision_fn(self, fn: DecisionFn) -> None:
        """Replace the agent's decision function."""
        self._decision_fn = fn

    # --- perception ---------------------------------------------------------

    def perceive(self, graph: RoomGraph) -> Dict[str, Any]:
        """Build a perception dict describing the agent's current room.

        Returns:
            A dict with keys ``room_id``, ``room_name``, ``description``,
            ``exits``, ``items``, ``npcs``, and ``inventory``.
        """
        room = graph.get(self.current_room)
        if room is None:
            return {
                "room_id": self.current_room,
                "room_name": "The Void",
                "description": "You are nowhere.",
                "exits": {},
                "items": [],
                "npcs": [],
                "inventory": [it.name for it in self.inventory],
            }
        return {
            "room_id": room.id,
            "room_name": room.name,
            "description": room.description,
            "exits": dict(room.exits),
            "items": list(room.items),
            "npcs": list(room.npcs),
            "inventory": [it.name for it in self.inventory],
        }

    # --- decision -----------------------------------------------------------

    def decide(self, perception: Dict[str, Any]) -> Command:
        """Run the decision function over the current perception."""
        return self._decision_fn(perception)

    # --- action execution ---------------------------------------------------

    def act(self, command: Command, graph: RoomGraph, bus: EventBus) -> str:
        """Execute a parsed command against the world.

        Supported verbs: :attr:`Verb.GO`, :attr:`Verb.LOOK`,
        :attr:`Verb.TAKE`, :attr:`Verb.DROP`, :attr:`Verb.USE`,
        :attr:`Verb.TALK`, :attr:`Verb.INVENTORY`, :attr:`Verb.HELP`.

        Args:
            command: The parsed command to execute.
            graph: The room graph for navigation and room state.
            bus: The event bus to emit events on.

        Returns:
            A human-readable result string describing the outcome.
        """
        verb = command.verb

        if verb == Verb.GO:
            return self._do_go(command.target, graph, bus)
        if verb == Verb.LOOK:
            return self._do_look(graph)
        if verb == Verb.TAKE:
            return self._do_take(command.target, graph, bus)
        if verb == Verb.DROP:
            return self._do_drop(command.target, graph, bus)
        if verb == Verb.USE:
            return self._do_use(command.target, command.indirect, bus)
        if verb == Verb.TALK:
            return self._do_talk(command.target, graph)
        if verb == Verb.INVENTORY:
            return self._do_inventory()
        if verb == Verb.EXAMINE:
            return self._do_examine(command.target, graph)
        if verb == Verb.HELP:
            return "Commands: go <dir>, look, examine <item>, take <item>, drop <item>, use <item> [with <target>], talk to <npc>, inventory, help, quit"
        if verb == Verb.QUIT:
            return "Goodbye."

        return f"Unknown command: {command.raw}"

    # --- verb implementations -----------------------------------------------

    def _do_go(self, direction: str, graph: RoomGraph, bus: EventBus) -> str:
        dest = graph.navigate(self.current_room, direction)
        if dest is None:
            return f"You can't go {direction}."
        old_room = self.current_room
        self.current_room = dest
        bus.emit(Event(
            type=EventType.ROOM_LEAVE,
            source=self.id,
            data={"from": old_room, "to": dest, "direction": direction},
            room=old_room,
        ))
        bus.emit(Event(
            type=EventType.ROOM_ENTER,
            source=self.id,
            data={"from": old_room, "to": dest, "direction": direction},
            room=dest,
        ))
        room = graph.get(dest)
        return room.description if room else f"You move {direction}."

    def _do_look(self, graph: RoomGraph) -> str:
        room = graph.get(self.current_room)
        if room is None:
            return "You are in the void."
        lines = [f"[{room.name}]", room.description]
        if room.exits:
            lines.append("Exits: " + ", ".join(room.exits))
        if room.items:
            lines.append("You see: " + ", ".join(room.items))
        if room.npcs:
            lines.append("Here: " + ", ".join(room.npcs))
        return "\n".join(lines)

    def _do_take(self, target: str, graph: RoomGraph, bus: EventBus) -> str:
        if not target:
            return "Take what?"
        room = graph.get(self.current_room)
        if room is None or target not in room.items:
            return f"You don't see {target} here."
        room.items.remove(target)
        self.inventory.add(__import__("mud_arena.inventory", fromlist=["Item"]).Item(name=target))
        bus.emit(Event(
            type=EventType.ITEM_PICKED_UP,
            source=self.id,
            data={"item": target},
            room=self.current_room,
        ))
        return f"You pick up {target}."

    def _do_drop(self, target: str, graph: RoomGraph, bus: EventBus) -> str:
        if not target:
            return "Drop what?"
        if not self.inventory.has(target):
            return f"You don't have {target}."
        self.inventory.remove(target)
        room = graph.get(self.current_room)
        if room is not None:
            room.items.append(target)
        bus.emit(Event(
            type=EventType.ITEM_DROPPED,
            source=self.id,
            data={"item": target},
            room=self.current_room,
        ))
        return f"You drop {target}."

    def _do_use(self, target: str, indirect: str, bus: EventBus) -> str:
        if not target:
            return "Use what?"
        if not self.inventory.has(target):
            return f"You don't have {target}."
        if not self.inventory.use(target):
            return f"You can't use {target}."
        detail = f" with {indirect}" if indirect else ""
        bus.emit(Event(
            type=EventType.ITEM_USED,
            source=self.id,
            data={"item": target, "indirect": indirect},
            room=self.current_room,
        ))
        return f"You use {target}{detail}."

    def _do_talk(self, target: str, graph: RoomGraph) -> str:
        if not target:
            return "Talk to whom?"
        room = graph.get(self.current_room)
        if room is not None and target in room.npcs:
            return f"{target} says: '...'"
        return f"You don't see {target} here."

    def _do_inventory(self) -> str:
        items = self.inventory.list_items()
        if not items:
            return "You are carrying nothing."
        names = ", ".join(it.name for it in items)
        return f"You are carrying: {names}"

    def _do_examine(self, target: str, graph: RoomGraph) -> str:
        if not target:
            return "Examine what?"
        # Check inventory first, then room
        item = self.inventory.get(target)
        if item is not None:
            return item.description
        room = graph.get(self.current_room)
        if room and target in room.items:
            return f"You see {target}. Nothing unusual."
        return f"You don't see {target} here."

    # --- full step ----------------------------------------------------------

    def step(self, graph: RoomGraph, bus: EventBus, command_text: str = "") -> str:
        """Run a full perceive-decide-act cycle.

        If *command_text* is provided it is parsed directly; otherwise the
        agent's decision function is called.
        """
        perception = self.perceive(graph)
        if command_text:
            command = parse_command(command_text)
        else:
            command = self.decide(perception)
        return self.act(command, graph, bus)
