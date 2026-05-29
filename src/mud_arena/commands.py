"""MUD command parser with support for common adventure-game verbs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class Verb(Enum):
    """Recognised MUD verbs."""

    GO = auto()
    LOOK = auto()
    EXAMINE = auto()
    TAKE = auto()
    DROP = auto()
    USE = auto()
    TALK = auto()
    INVENTORY = auto()
    HELP = auto()
    QUIT = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class Command:
    """A parsed MUD command.

    Attributes:
        verb: The action verb.
        target: Primary target (e.g. item or NPC name).
        indirect: Secondary target for three-part commands like ``use X with Y``.
        raw: The original input string.
    """

    verb: Verb
    target: str = ""
    indirect: str = ""
    raw: str = ""


# Preposition sets used to split three-part commands.
_WITH_PREPS = frozenset({"with", "on", "to", "at", "upon"})
_TALK_PREPS = frozenset({"to", "with"})


def parse_command(text: str) -> Command:
    """Parse a MUD command string into a structured :class:`Command`.

    Supported forms::

        go north
        look
        examine crystal_ball
        take key
        drop sword
        use key with door
        talk to guard
        inventory
        help
        quit

    Args:
        text: Raw player/agent input.

    Returns:
        A :class:`Command` with the verb, target, and optional indirect
        object filled in.
    """
    raw = text.strip()
    if not raw:
        return Command(verb=Verb.UNKNOWN, raw=raw)

    parts = raw.lower().split()
    first = parts[0]

    # --- one-word commands ---------------------------------------------------
    if first in ("look", "l"):
        return Command(verb=Verb.LOOK, raw=raw)
    if first in ("inventory", "i", "inv"):
        return Command(verb=Verb.INVENTORY, raw=raw)
    if first == "help":
        return Command(verb=Verb.HELP, raw=raw)
    if first in ("quit", "exit", "q"):
        return Command(verb=Verb.QUIT, raw=raw)

    # --- two-word commands ---------------------------------------------------
    if first in ("go", "move", "walk", "run", "head"):
        direction = parts[1] if len(parts) > 1 else ""
        return Command(verb=Verb.GO, target=direction, raw=raw)

    if first in ("examine", "x", "inspect"):
        target = " ".join(parts[1:]) if len(parts) > 1 else ""
        return Command(verb=Verb.EXAMINE, target=target, raw=raw)

    if first in ("take", "get", "pick", "grab"):
        # "pick up X" → target = X
        rest = parts[1:]
        if rest and rest[0] == "up":
            rest = rest[1:]
        target = " ".join(rest)
        return Command(verb=Verb.TAKE, target=target, raw=raw)

    if first == "drop":
        target = " ".join(parts[1:]) if len(parts) > 1 else ""
        return Command(verb=Verb.DROP, target=target, raw=raw)

    # --- three-part: use X with/on Y ----------------------------------------
    if first == "use":
        return _parse_three_part(parts[1:], Verb.USE, raw)

    # --- three-part: talk to/with X ------------------------------------------
    if first == "talk":
        return _parse_talk(parts[1:], raw)

    # --- direction shorthand: just "north", "south", etc. --------------------
    if first in ("north", "south", "east", "west", "n", "s", "e", "w",
                 "northeast", "nw", "southeast", "sw", "northeast", "ne",
                 "northwest", "southwest", "up", "down", "in", "out"):
        return Command(verb=Verb.GO, target=first, raw=raw)

    return Command(verb=Verb.UNKNOWN, target=raw, raw=raw)


def _parse_three_part(rest: list[str], verb: Verb, raw: str) -> Command:
    """Parse ``X with Y`` style commands."""
    target_parts: list[str] = []
    indirect_parts: list[str] = []
    found_prep = False
    for word in rest:
        if not found_prep and word in _WITH_PREPS:
            found_prep = True
            continue
        if found_prep:
            indirect_parts.append(word)
        else:
            target_parts.append(word)
    return Command(
        verb=verb,
        target=" ".join(target_parts),
        indirect=" ".join(indirect_parts),
        raw=raw,
    )


def _parse_talk(rest: list[str], raw: str) -> Command:
    """Parse ``talk to/with X``."""
    filtered = [w for w in rest if w not in _TALK_PREPS]
    return Command(verb=Verb.TALK, target=" ".join(filtered), raw=raw)
