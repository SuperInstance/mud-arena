"""Tests for the MUD command parser."""

from mud_arena.commands import Verb, parse_command


class TestCommandParsing:
    """Parse various MUD command forms."""

    def test_go_direction(self) -> None:
        cmd = parse_command("go north")
        assert cmd.verb == Verb.GO
        assert cmd.target == "north"

    def test_look(self) -> None:
        cmd = parse_command("look")
        assert cmd.verb == Verb.LOOK

    def test_examine_crystal_ball(self) -> None:
        cmd = parse_command("examine crystal_ball")
        assert cmd.verb == Verb.EXAMINE
        assert cmd.target == "crystal_ball"

    def test_use_key_with_door(self) -> None:
        cmd = parse_command("use key with door")
        assert cmd.verb == Verb.USE
        assert cmd.target == "key"
        assert cmd.indirect == "door"

    def test_talk_to_guard(self) -> None:
        cmd = parse_command("talk to guard")
        assert cmd.verb == Verb.TALK
        assert cmd.target == "guard"

    def test_direction_shorthand(self) -> None:
        cmd = parse_command("north")
        assert cmd.verb == Verb.GO
        assert cmd.target == "north"

    def test_inventory_aliases(self) -> None:
        for alias in ("inventory", "i", "inv"):
            cmd = parse_command(alias)
            assert cmd.verb == Verb.INVENTORY, f"{alias} should parse as INVENTORY"

    def test_unknown_command(self) -> None:
        cmd = parse_command("dance wildly")
        assert cmd.verb == Verb.UNKNOWN

    def test_empty_input(self) -> None:
        cmd = parse_command("")
        assert cmd.verb == Verb.UNKNOWN

    def test_take_item(self) -> None:
        cmd = parse_command("take sword")
        assert cmd.verb == Verb.TAKE
        assert cmd.target == "sword"

    def test_pick_up_item(self) -> None:
        cmd = parse_command("pick up coin")
        assert cmd.verb == Verb.TAKE
        assert cmd.target == "coin"

    def test_drop_item(self) -> None:
        cmd = parse_command("drop sword")
        assert cmd.verb == Verb.DROP
        assert cmd.target == "sword"
