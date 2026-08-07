"""
Comprehensive tests for the MUD Arena Script Compiler.

Covers: DSL parsing, validation, random generation, mutation, breeding,
binary serialization round-trips, DSL round-trips, and error paths.
"""

import pytest
import struct
import random
from src.script_compiler import (
    ScriptCompiler,
    ScriptRule,
    Script,
    ConditionType,
    ActionType,
    ITEM_IDS,
    EXIT_IDS,
    TARGET_IDS,
    DIRECTION_IDS,
)


# ---------------------------------------------------------------------------
#  Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_dsl():
    return '''"TestScript"
WHEN hp < 30% AND enemy_in_room THEN flee random_exit
WHEN hp >= 50% AND enemy_in_room THEN attack weakest
WHEN item_on_ground THEN pickup
WHEN gold_on_ground THEN pickup gold
WHEN inventory_not_full AND turns > 20 THEN move north
DEFAULT move random_exit'''


@pytest.fixture
def sample_script(sample_dsl):
    return ScriptCompiler.parse(sample_dsl)


@pytest.fixture
def simple_dsl():
    return '''"Simple"
WHEN enemy_in_room THEN attack weakest
DEFAULT move random_exit'''


@pytest.fixture
def simple_script(simple_dsl):
    return ScriptCompiler.parse(simple_dsl)


# ---------------------------------------------------------------------------
#  1. Parse: basic structure
# ---------------------------------------------------------------------------
class TestParseBasic:
    def test_script_has_name(self, sample_script):
        assert sample_script.name == "TestScript"

    def test_script_has_correct_rule_count(self, sample_script):
        assert len(sample_script.rules) == 6

    def test_rules_have_sequential_priorities(self, sample_script):
        priorities = [r.priority for r in sample_script.rules]
        assert priorities == list(range(6))

    def test_unquoted_name(self):
        script = ScriptCompiler.parse("MyScript\nDEFAULT move north")
        assert script.name == "MyScript"

    def test_empty_dsl_raises(self):
        with pytest.raises(ValueError, match="Empty DSL"):
            ScriptCompiler.parse("")

    def test_whitespace_only_dsl_raises(self):
        with pytest.raises(ValueError, match="Empty DSL"):
            ScriptCompiler.parse("   \n  \n  ")

    def test_blank_lines_ignored(self):
        dsl = '"Test"\n\nWHEN enemy_in_room THEN attack weakest\n\nDEFAULT move north\n'
        script = ScriptCompiler.parse(dsl)
        assert len(script.rules) == 2


# ---------------------------------------------------------------------------
#  2. Parse: conditions
# ---------------------------------------------------------------------------
class TestParseConditions:
    def test_hp_below(self):
        script = ScriptCompiler.parse('"S"\nWHEN hp < 50% THEN flee random_exit')
        rule = script.rules[0]
        assert rule.condition_type == ConditionType.HP_BELOW
        assert rule.condition_param & 0xFF == 50

    def test_hp_above_or_equal(self):
        script = ScriptCompiler.parse('"S"\nWHEN hp >= 70% THEN attack weakest')
        rule = script.rules[0]
        assert rule.condition_type == ConditionType.HP_ABOVE_OR_EQUAL
        assert rule.condition_param & 0xFF == 70

    def test_turns_above(self):
        script = ScriptCompiler.parse('"S"\nWHEN turns > 15 THEN move north')
        rule = script.rules[0]
        assert rule.condition_type == ConditionType.TURNS_ABOVE
        assert rule.condition_param & 0xFF == 15

    def test_enemy_present_flag(self):
        script = ScriptCompiler.parse('"S"\nWHEN enemy_in_room THEN attack weakest')
        rule = script.rules[0]
        # No primary condition, so type is ENEMY_PRESENT with extra_mask
        assert rule.condition_type == ConditionType.ENEMY_PRESENT
        assert rule.condition_param & 0x01  # bit 0 set

    def test_item_on_ground_flag(self):
        script = ScriptCompiler.parse('"S"\nWHEN item_on_ground THEN pickup')
        rule = script.rules[0]
        assert rule.condition_param & (1 << 1)  # bit 1 set

    def test_gold_on_ground_flag(self):
        script = ScriptCompiler.parse('"S"\nWHEN gold_on_ground THEN pickup gold')
        rule = script.rules[0]
        assert rule.condition_param & (1 << 2)  # bit 2 set

    def test_inventory_not_full_flag(self):
        script = ScriptCompiler.parse('"S"\nWHEN inventory_not_full THEN pickup')
        rule = script.rules[0]
        assert rule.condition_param & (1 << 3)  # bit 3 set

    def test_combined_hp_and_flag(self):
        script = ScriptCompiler.parse('"S"\nWHEN hp < 40% AND enemy_in_room THEN flee random_exit')
        rule = script.rules[0]
        assert rule.condition_type == ConditionType.HP_BELOW
        # HP value in low byte, extra mask in high byte
        assert rule.condition_param & 0xFF == 40
        assert (rule.condition_param >> 8) & 0x01  # enemy_in_room bit set

    def test_multiple_flags_combined(self):
        script = ScriptCompiler.parse('"S"\nWHEN enemy_in_room AND gold_on_ground AND inventory_not_full THEN pickup gold')
        rule = script.rules[0]
        mask = rule.condition_param
        assert mask & 0x01  # enemy
        assert mask & 0x04  # gold
        assert mask & 0x08  # inventory

    def test_unknown_condition_raises(self):
        with pytest.raises(ValueError, match="Unknown condition token"):
            ScriptCompiler.parse('"S"\nWHEN banana THEN attack weakest')


# ---------------------------------------------------------------------------
#  3. Parse: actions
# ---------------------------------------------------------------------------
class TestParseActions:
    def test_use_item_valid(self):
        script = ScriptCompiler.parse('"S"\nWHEN hp < 50% THEN use_item health_potion')
        assert script.rules[0].action_type == ActionType.USE_ITEM
        assert script.rules[0].action_param == ITEM_IDS["health_potion"]

    def test_use_item_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown item"):
            ScriptCompiler.parse('"S"\nWHEN hp < 50% THEN use_item banana_potion')

    def test_flee_valid(self):
        script = ScriptCompiler.parse('"S"\nWHEN enemy_in_room THEN flee north')
        assert script.rules[0].action_type == ActionType.FLEE
        assert script.rules[0].action_param == EXIT_IDS["north"]

    def test_flee_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown exit"):
            ScriptCompiler.parse('"S"\nWHEN enemy_in_room THEN flee diagonally')

    def test_pickup_generic(self):
        script = ScriptCompiler.parse('"S"\nWHEN item_on_ground THEN pickup')
        assert script.rules[0].action_type == ActionType.PICKUP
        assert script.rules[0].action_param == 0

    def test_pickup_gold(self):
        script = ScriptCompiler.parse('"S"\nWHEN gold_on_ground THEN pickup gold')
        assert script.rules[0].action_type == ActionType.PICKUP
        assert script.rules[0].action_param == 1

    def test_attack_valid(self):
        script = ScriptCompiler.parse('"S"\nWHEN enemy_in_room THEN attack weakest')
        assert script.rules[0].action_type == ActionType.ATTACK
        assert script.rules[0].action_param == TARGET_IDS["weakest"]

    def test_attack_unknown_target_raises(self):
        with pytest.raises(ValueError, match="Unknown attack target"):
            ScriptCompiler.parse('"S"\nWHEN enemy_in_room THEN attack loudest')

    def test_move_valid(self):
        script = ScriptCompiler.parse('"S"\nWHEN turns > 5 THEN move north')
        assert script.rules[0].action_type == ActionType.MOVE
        assert script.rules[0].action_param == DIRECTION_IDS["north"]

    def test_move_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown move direction"):
            ScriptCompiler.parse('"S"\nWHEN turns > 5 THEN move sideways')

    def test_empty_action_raises(self):
        with pytest.raises(ValueError, match="Empty action"):
            ScriptCompiler.parse('"S"\nWHEN enemy_in_room THEN')

    def test_unsupported_verb_raises(self):
        with pytest.raises(ValueError, match="Unsupported action verb"):
            ScriptCompiler.parse('"S"\nWHEN enemy_in_room THEN dance wildly')


# ---------------------------------------------------------------------------
#  4. Parse: syntax errors
# ---------------------------------------------------------------------------
class TestParseErrors:
    def test_line_without_when_or_default_raises(self):
        with pytest.raises(ValueError, match="does not start with WHEN or DEFAULT"):
            ScriptCompiler.parse('"S"\nDO SOMETHING')

    def test_missing_then_raises(self):
        with pytest.raises(ValueError, match="Missing THEN"):
            ScriptCompiler.parse('"S"\nWHEN enemy_in_room attack weakest')

    def test_missing_then_in_when_line(self):
        with pytest.raises(ValueError, match="Missing THEN"):
            ScriptCompiler.parse('"S"\nWHEN hp < 30% AND enemy_in_room flee north')


# ---------------------------------------------------------------------------
#  5. Validation: contradictory conditions
# ---------------------------------------------------------------------------
class TestValidation:
    def test_contradictory_hp_raises(self):
        with pytest.raises(ValueError, match="Contradictory HP condition"):
            ScriptCompiler.parse('"S"\nWHEN hp < 30% AND hp >= 30% THEN flee random_exit')

    def test_contradictory_hp_different_values_raises(self):
        with pytest.raises(ValueError, match="Contradictory HP condition"):
            ScriptCompiler.parse('"S"\nWHEN hp < 20% AND hp >= 80% THEN flee random_exit')

    def test_non_contradictory_hp_ok(self):
        # hp < 30% AND hp >= 10% is valid (ranges can overlap in the allowed direction)
        script = ScriptCompiler.parse('"S"\nWHEN hp < 30% AND hp >= 10% THEN use_item health_potion')
        assert len(script.rules) == 1


# ---------------------------------------------------------------------------
#  6. Random generation
# ---------------------------------------------------------------------------
class TestRandomGeneration:
    def test_generates_valid_script(self):
        script = ScriptCompiler.generate_random()
        assert isinstance(script, Script)
        assert len(script.rules) >= 4  # 3-8 rules + 1 default

    def test_random_script_has_default_rule(self):
        script = ScriptCompiler.generate_random()
        assert script.rules[-1].condition_type == ConditionType.DEFAULT

    def test_random_script_priorities_sequential(self):
        script = ScriptCompiler.generate_random()
        priorities = [r.priority for r in script.rules]
        assert priorities == list(range(len(script.rules)))

    def test_random_script_name_starts_with_random(self):
        script = ScriptCompiler.generate_random()
        assert script.name.startswith("Random_")

    def test_random_script_rules_are_valid_types(self):
        script = ScriptCompiler.generate_random()
        for rule in script.rules:
            assert isinstance(rule.condition_type, int)
            assert isinstance(rule.action_type, int)
            assert isinstance(rule.condition_param, int)
            assert isinstance(rule.action_param, int)


# ---------------------------------------------------------------------------
#  7. Mutation
# ---------------------------------------------------------------------------
class TestMutation:
    def test_mutate_returns_new_script(self, sample_script):
        random.seed(42)
        mutated = ScriptCompiler.mutate(sample_script, rate=0.5)
        assert mutated is not sample_script
        assert mutated.name == sample_script.name + "_mut"

    def test_mutate_preserves_fitness(self, sample_script):
        sample_script.fitness = 0.75
        mutated = ScriptCompiler.mutate(sample_script, rate=0.0)
        assert mutated.fitness == 0.75

    def test_mutate_zero_rate_keeps_rules_count(self, sample_script):
        random.seed(42)
        mutated = ScriptCompiler.mutate(sample_script, rate=0.0)
        assert len(mutated.rules) == len(sample_script.rules)

    def test_mutate_priorities_sequential(self, sample_script):
        random.seed(42)
        mutated = ScriptCompiler.mutate(sample_script, rate=0.8)
        priorities = [r.priority for r in mutated.rules]
        assert priorities == list(range(len(mutated.rules)))

    def test_mutate_does_not_modify_original(self, sample_script):
        original_count = len(sample_script.rules)
        random.seed(42)
        ScriptCompiler.mutate(sample_script, rate=0.9)
        assert len(sample_script.rules) == original_count


# ---------------------------------------------------------------------------
#  8. Breeding
# ---------------------------------------------------------------------------
class TestBreeding:
    def test_breed_returns_script(self, sample_script):
        parent_b = ScriptCompiler.generate_random()
        random.seed(42)
        child = ScriptCompiler.breed(sample_script, parent_b)
        assert isinstance(child, Script)

    def test_breed_child_has_default_rule(self, sample_script):
        parent_b = ScriptCompiler.generate_random()
        random.seed(42)
        child = ScriptCompiler.breed(sample_script, parent_b)
        assert child.rules[-1].condition_type == ConditionType.DEFAULT

    def test_breed_child_priorities_sequential(self, sample_script):
        parent_b = ScriptCompiler.generate_random()
        random.seed(42)
        child = ScriptCompiler.breed(sample_script, parent_b)
        priorities = [r.priority for r in child.rules]
        assert priorities == list(range(len(child_rules := child.rules)))

    def test_breed_missing_default_parent_a_raises(self):
        bad_parent = Script(name="Bad", rules=[ScriptRule(1, 0, 1, 0, 0)])
        good_parent = ScriptCompiler.generate_random()
        with pytest.raises(ValueError, match="Parent A missing default"):
            ScriptCompiler.breed(bad_parent, good_parent)

    def test_breed_missing_default_parent_b_raises(self):
        good_parent = ScriptCompiler.generate_random()
        bad_parent = Script(name="Bad", rules=[ScriptRule(1, 0, 1, 0, 0)])
        with pytest.raises(ValueError, match="Parent B missing default"):
            ScriptCompiler.breed(good_parent, bad_parent)

    def test_breed_child_name_combines_parents(self, sample_script):
        parent_b = ScriptCompiler.generate_random()
        random.seed(42)
        child = ScriptCompiler.breed(sample_script, parent_b)
        assert sample_script.name in child.name
        assert parent_b.name in child.name


# ---------------------------------------------------------------------------
#  9. Binary serialization round-trip
# ---------------------------------------------------------------------------
class TestBinarySerialization:
    def test_to_binary_returns_bytes(self, sample_script):
        data = ScriptCompiler.to_binary(sample_script)
        assert isinstance(data, bytes)

    def test_to_binary_starts_with_rule_count(self, sample_script):
        data = ScriptCompiler.to_binary(sample_script)
        (count,) = struct.unpack_from("<i", data, 0)
        assert count == len(sample_script.rules)

    def test_roundtrip_preserves_rules(self, sample_script):
        data = ScriptCompiler.to_binary(sample_script)
        restored = ScriptCompiler.from_binary(data)
        assert len(restored.rules) == len(sample_script.rules)
        for orig, rest in zip(sample_script.rules, restored.rules):
            assert rest.condition_type == orig.condition_type
            assert rest.condition_param == orig.condition_param
            assert rest.action_type == orig.action_type
            assert rest.action_param == orig.action_param
            assert rest.priority == orig.priority

    def test_roundtrip_name_is_binary(self, sample_script):
        data = ScriptCompiler.to_binary(sample_script)
        restored = ScriptCompiler.from_binary(data)
        assert restored.name == "<binary>"

    def test_binary_size_matches_formula(self, sample_script):
        data = ScriptCompiler.to_binary(sample_script)
        expected = 4 + 20 * len(sample_script.rules)  # header + 5 int32s per rule
        assert len(data) == expected

    def test_roundtrip_simple_script(self, simple_script):
        data = ScriptCompiler.to_binary(simple_script)
        restored = ScriptCompiler.from_binary(data)
        assert len(restored.rules) == len(simple_script.rules)


# ---------------------------------------------------------------------------
# 10. DSL round-trip (to_dsl)
# ---------------------------------------------------------------------------
class TestDSLRoundTrip:
    def test_to_dsl_includes_name(self, sample_script):
        dsl = ScriptCompiler.to_dsl(sample_script)
        assert '"TestScript"' in dsl

    def test_to_dsl_includes_default(self, sample_script):
        dsl = ScriptCompiler.to_dsl(sample_script)
        assert "DEFAULT" in dsl

    def test_to_dsl_includes_when(self, sample_script):
        dsl = ScriptCompiler.to_dsl(sample_script)
        assert "WHEN" in dsl

    def test_to_dsl_rules_in_priority_order(self, simple_script):
        dsl = ScriptCompiler.to_dsl(simple_script)
        lines = [l.strip() for l in dsl.splitlines() if l.strip()]
        # First line is name, second should be the WHEN rule (priority 0)
        assert lines[1].startswith("WHEN")
        # Last line should be the DEFAULT rule (highest priority = last)
        assert lines[-1].startswith("DEFAULT")

    def test_action_to_str_use_item(self):
        rule = ScriptRule(
            condition_type=ConditionType.DEFAULT,
            condition_param=0,
            action_type=ActionType.USE_ITEM,
            action_param=ITEM_IDS["health_potion"],
            priority=0,
        )
        s = Script("test", [rule])
        dsl = ScriptCompiler.to_dsl(s)
        assert "use_item health_potion" in dsl

    def test_action_to_str_flee(self):
        rule = ScriptRule(
            condition_type=ConditionType.DEFAULT,
            condition_param=0,
            action_type=ActionType.FLEE,
            action_param=EXIT_IDS["north"],
            priority=0,
        )
        s = Script("test", [rule])
        dsl = ScriptCompiler.to_dsl(s)
        assert "flee north" in dsl

    def test_action_to_str_pickup_gold(self):
        rule = ScriptRule(
            condition_type=ConditionType.DEFAULT,
            condition_param=0,
            action_type=ActionType.PICKUP,
            action_param=1,
            priority=0,
        )
        s = Script("test", [rule])
        dsl = ScriptCompiler.to_dsl(s)
        assert "pickup gold" in dsl

    def test_action_to_str_pickup_generic(self):
        rule = ScriptRule(
            condition_type=ConditionType.DEFAULT,
            condition_param=0,
            action_type=ActionType.PICKUP,
            action_param=0,
            priority=0,
        )
        s = Script("test", [rule])
        dsl = ScriptCompiler.to_dsl(s)
        assert "pickup" in dsl

    def test_action_to_str_attack(self):
        rule = ScriptRule(
            condition_type=ConditionType.DEFAULT,
            condition_param=0,
            action_type=ActionType.ATTACK,
            action_param=TARGET_IDS["strongest"],
            priority=0,
        )
        s = Script("test", [rule])
        dsl = ScriptCompiler.to_dsl(s)
        assert "attack strongest" in dsl

    def test_action_to_str_move(self):
        rule = ScriptRule(
            condition_type=ConditionType.DEFAULT,
            condition_param=0,
            action_type=ActionType.MOVE,
            action_param=DIRECTION_IDS["north"],
            priority=0,
        )
        s = Script("test", [rule])
        dsl = ScriptCompiler.to_dsl(s)
        assert "move north" in dsl

    def test_condition_to_str_hp_below(self):
        rule = ScriptRule(
            condition_type=ConditionType.HP_BELOW,
            condition_param=40,
            action_type=ActionType.FLEE,
            action_param=EXIT_IDS["random_exit"],
            priority=0,
        )
        s = Script("test", [rule])
        dsl = ScriptCompiler.to_dsl(s)
        assert "hp < 40%" in dsl

    def test_condition_to_str_hp_above(self):
        rule = ScriptRule(
            condition_type=ConditionType.HP_ABOVE_OR_EQUAL,
            condition_param=70,
            action_type=ActionType.ATTACK,
            action_param=TARGET_IDS["weakest"],
            priority=0,
        )
        s = Script("test", [rule])
        dsl = ScriptCompiler.to_dsl(s)
        assert "hp >= 70%" in dsl

    def test_condition_to_str_turns(self):
        rule = ScriptRule(
            condition_type=ConditionType.TURNS_ABOVE,
            condition_param=20,
            action_type=ActionType.MOVE,
            action_param=DIRECTION_IDS["north"],
            priority=0,
        )
        s = Script("test", [rule])
        dsl = ScriptCompiler.to_dsl(s)
        assert "turns > 20" in dsl

    def test_condition_to_str_with_extra_flags(self):
        # HP_BELOW with enemy_in_room flag in extra mask
        param = 40 | (1 << 8)  # hp < 40% with enemy_in_room
        rule = ScriptRule(
            condition_type=ConditionType.HP_BELOW,
            condition_param=param,
            action_type=ActionType.FLEE,
            action_param=EXIT_IDS["random_exit"],
            priority=0,
        )
        s = Script("test", [rule])
        dsl = ScriptCompiler.to_dsl(s)
        assert "hp < 40%" in dsl
        assert "enemy_in_room" in dsl


# ---------------------------------------------------------------------------
# 11. Full round-trip: parse → to_binary → from_binary → to_dsl
# ---------------------------------------------------------------------------
class TestFullRoundTrip:
    def test_parse_to_binary_to_dsl_preserves_actions(self, sample_dsl):
        script = ScriptCompiler.parse(sample_dsl)
        data = ScriptCompiler.to_binary(script)
        restored = ScriptCompiler.from_binary(data)
        dsl = ScriptCompiler.to_dsl(restored)
        assert "flee random_exit" in dsl
        assert "attack weakest" in dsl
        assert "pickup gold" in dsl

    def test_generate_random_to_binary_roundtrip(self):
        for seed in range(10):
            random.seed(seed)
            script = ScriptCompiler.generate_random()
            data = ScriptCompiler.to_binary(script)
            restored = ScriptCompiler.from_binary(data)
            assert len(restored.rules) == len(script.rules)

    def test_mutate_then_serialize(self, sample_script):
        random.seed(99)
        mutated = ScriptCompiler.mutate(sample_script, rate=0.5)
        data = ScriptCompiler.to_binary(mutated)
        restored = ScriptCompiler.from_binary(data)
        assert len(restored.rules) == len(mutated.rules)


# ---------------------------------------------------------------------------
# 12. Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_script_with_only_default_rule(self):
        script = ScriptCompiler.parse('"OnlyDefault"\nDEFAULT attack weakest')
        assert len(script.rules) == 1
        assert script.rules[0].condition_type == ConditionType.DEFAULT

    def test_script_with_single_when_rule(self, simple_script):
        assert len(simple_script.rules) == 2  # one WHEN + one DEFAULT

    def test_all_item_ids_covered(self):
        assert "health_potion" in ITEM_IDS
        assert "mana_potion" in ITEM_IDS
        assert "elixir" in ITEM_IDS

    def test_all_exit_ids_covered(self):
        for exit_name in ["random_exit", "north", "south", "east", "west"]:
            assert exit_name in EXIT_IDS

    def test_all_target_ids_covered(self):
        for target in ["weakest", "strongest", "nearest"]:
            assert target in TARGET_IDS

    def test_all_direction_ids_covered(self):
        for direction in ["random_exit", "toward town", "away from town", "north", "south", "east", "west"]:
            assert direction in DIRECTION_IDS

    def test_script_rule_repr(self):
        rule = ScriptRule(0, 50, 3, 0, 1)
        repr_str = repr(rule)
        assert "ScriptRule" in repr_str
        assert "cond=0" in repr_str

    def test_mutation_rate_zero(self, sample_script):
        random.seed(42)
        mutated = ScriptCompiler.mutate(sample_script, rate=0.0)
        # With rate=0, rules should be identical (copied)
        for orig, mut in zip(sample_script.rules, mutated.rules):
            assert mut.condition_type == orig.condition_type
            assert mut.action_type == orig.action_type
            assert mut.action_param == orig.action_param
