"""Inventory system — items that agents can carry, use, and trade."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Item:
    """An item in the MUD world.

    Attributes:
        name: Unique item name (used as key in inventories).
        description: Flavor text.
        usable: Whether the item can be ``use``d.
        uses: Number of remaining uses (``-1`` = unlimited).
        tags: Arbitrary tags for categorisation (e.g. ``"key"``, ``"weapon"``).
    """

    name: str
    description: str = "A nondescript item."
    usable: bool = True
    uses: int = -1
    tags: List[str] = field(default_factory=list)

    def use(self) -> bool:
        """Consume one use of the item.

        Returns:
            ``True`` if the item was used successfully, ``False`` if no
            uses remain.
        """
        if not self.usable:
            return False
        if self.uses == 0:
            return False
        if self.uses > 0:
            self.uses -= 1
        return True

    def has_tag(self, tag: str) -> bool:
        """Check whether the item has a given tag."""
        return tag in self.tags


class Inventory:
    """A container of :class:`Item` objects with capacity tracking.

    Args:
        capacity: Maximum number of items.  ``0`` means unlimited.
    """

    def __init__(self, capacity: int = 0) -> None:
        self._items: Dict[str, Item] = {}
        self.capacity = capacity

    def add(self, item: Item) -> bool:
        """Add an item to the inventory.

        Returns:
            ``False`` if capacity is exceeded.
        """
        if self.capacity > 0 and len(self._items) >= self.capacity:
            return False
        self._items[item.name] = item
        return True

    def remove(self, name: str) -> Optional[Item]:
        """Remove and return an item by name; ``None`` if not carried."""
        return self._items.pop(name, None)

    def get(self, name: str) -> Optional[Item]:
        """Look up an item without removing it."""
        return self._items.get(name)

    def has(self, name: str) -> bool:
        """Check if an item is in the inventory."""
        return name in self._items

    def list_items(self) -> List[Item]:
        """Return all items as a list."""
        return list(self._items.values())

    def find_by_tag(self, tag: str) -> List[Item]:
        """Return all items matching a given tag."""
        return [it for it in self._items.values() if it.has_tag(tag)]

    def use(self, name: str) -> bool:
        """Use an item by name.

        If the item's uses drop to zero it is automatically removed.

        Returns:
            ``True`` if the item was used, ``False`` if not found or
            not usable.
        """
        item = self._items.get(name)
        if item is None:
            return False
        if not item.use():
            return False
        if item.uses == 0:
            self._items.pop(name, None)
        return True

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, name: str) -> bool:
        return name in self._items

    def __iter__(self):
        return iter(self._items.values())
