"""Tests for the inventory system."""

from mud_arena.inventory import Inventory, Item


class TestInventory:
    def test_add_and_list(self) -> None:
        inv = Inventory()
        inv.add(Item(name="sword", description="A sharp blade.", tags=["weapon"]))
        inv.add(Item(name="potion", description="Heals 50 HP.", uses=3, tags=["consumable"]))
        assert len(inv) == 2
        names = [it.name for it in inv.list_items()]
        assert "sword" in names
        assert "potion" in names

    def test_remove_item(self) -> None:
        inv = Inventory()
        inv.add(Item(name="key"))
        removed = inv.remove("key")
        assert removed is not None
        assert removed.name == "key"
        assert len(inv) == 0

    def test_remove_nonexistent(self) -> None:
        inv = Inventory()
        assert inv.remove("nothing") is None

    def test_has_item(self) -> None:
        inv = Inventory()
        inv.add(Item(name="map"))
        assert inv.has("map")
        assert not inv.has("compass")

    def test_use_consumable(self) -> None:
        inv = Inventory()
        inv.add(Item(name="potion", uses=3))
        assert inv.use("potion") is True
        item = inv.get("potion")
        assert item is not None
        assert item.uses == 2

    def test_use_depleted_item_removed(self) -> None:
        inv = Inventory()
        inv.add(Item(name="scroll", uses=1))
        inv.use("scroll")
        assert not inv.has("scroll")

    def test_capacity_limit(self) -> None:
        inv = Inventory(capacity=2)
        assert inv.add(Item(name="a"))
        assert inv.add(Item(name="b"))
        assert not inv.add(Item(name="c"))  # exceeds capacity

    def test_find_by_tag(self) -> None:
        inv = Inventory()
        inv.add(Item(name="sword", tags=["weapon"]))
        inv.add(Item(name="dagger", tags=["weapon"]))
        inv.add(Item(name="bread", tags=["food"]))
        weapons = inv.find_by_tag("weapon")
        assert len(weapons) == 2
