"""
mud_arena — Agent simulation arena with MUD mechanics.

Provides core MUD-world primitives: rooms, exits, items, inventories,
command parsing, agent perception/decision loops, and an event system.
Designed as the simulation substrate for OpenConstruct terrain/a2ui agents.

Part of the SuperInstance OpenConstruct ecosystem.
"""

from mud_arena.commands import Command, parse_command
from mud_arena.rooms import Room, RoomGraph
from mud_arena.inventory import Inventory, Item
from mud_arena.agent import Agent
from mud_arena.events import Event, EventBus

__all__ = [
    "Command",
    "parse_command",
    "Room",
    "RoomGraph",
    "Inventory",
    "Item",
    "Agent",
    "Event",
    "EventBus",
]
