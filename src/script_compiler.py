Below is a **self‑contained Python module** that implements the requested MUD‑Arena script compiler.  
All eight features are present:

1. **DSL → `ScriptRule` list** (`parse`)  
2. **Simple validation** (`_validate_rule`)  
3. **Random script generation** (`generate_random`)  
4. **Mutation** (`mutate`)  
5. **Crossover / breeding** (`breed`)  
6. **Binary export** (`to_binary`)  
7. **Binary import** (`from_binary`)  
8. **Pretty‑print back to DSL** (`to_dsl`)

The code is heavily commented and uses `dataclasses`, `Enum`s and type hints for clarity.  
Feel free to copy the whole file into a `.py` file and import `ScriptCompiler` in your project.

```python
#!/usr/bin/env python3
"""
MUD‑Arena Script Compiler
-------------------------

A tiny DSL is used by agents to describe their behaviour.  The compiler
turns the DSL into a list of ``ScriptRule`` objects that can be uploaded
to the GPU as a compact binary blob.

Features
~~~~~~~~
1. parse(dsl_text)                → Script
2. generate_random()              → Script
3. mutate(script, rate=0.1)       → Script
4. breed(parent_a, parent_b)      → Script
5. to_binary(script)              → bytes
6. from_binary(data)              → Script
7. to_dsl(script)                 → str
8. internal validation of rules
"""

import random
import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Tuple, Dict, Optional

# --------------------------------------------------------------------------- #
#  Enumerations – keep the integer values stable because they are written to
#  the GPU binary format.
# --------------------------------------------------------------------------- #
class ConditionType(IntEnum):
    HP_BELOW = 0          # hp < X%
    HP_ABOVE_OR_EQUAL = 1 # hp >= X%
    ENEMY_PRESENT = 2     # enemy_in_room
    ITEM_ON_GROUND = 3    # item_on_ground
    GOLD_ON_GROUND = 4    # gold_on_ground
    TURNS_ABOVE = 5       # turns > X
    INVENTORY_NOT_FULL = 6# inventory_not_full
    DEFAULT = -1          # default rule (no condition)


class ActionType(IntEnum):
    USE_ITEM = 0
    FLEE = 1
    PICKUP = 2
    ATTACK = 3
    MOVE = 4


# --------------------------------------------------------------------------- #
#  Helper tables – map textual identifiers to integer IDs that are stored in
#  the binary format.  They can be extended without touching the rest of the
#  code.
# --------------------------------------------------------------------------- #
ITEM_IDS: Dict[str, int] = {
    "health_potion": 0,
    "mana_potion": 1,
    "elixir": 2,
}
EXIT_IDS: Dict[str, int] = {
    "random_exit": 0,
    "north": 1,
    "south": 2,
    "east": 3,
    "west": 4,
}
TARGET_IDS: Dict[str, int] = {
    "weakest": 0,
    "strongest": 1,
    "nearest": 2,
}
DIRECTION_IDS: Dict[str, int] = {
    "random_exit": 0,
    "toward town": 1,
    "away from town": 2,
    "north": 3,
    "south": 4,
    "east": 5,
    "west": 6,
}


def _reverse_lookup(table: Dict[str, int]) -> Dict[int, str]:
    return {v: k for k, v in table.items()}


ITEM_IDS_REV = _reverse_lookup(ITEM_IDS)
EXIT_IDS_REV = _reverse_lookup(EXIT_IDS)
TARGET_IDS_REV = _reverse_lookup(TARGET_IDS)
DIRECTION_IDS_REV = _reverse_lookup(DIRECTION_IDS)


# --------------------------------------------------------------------------- #
#  Core data structures
# --------------------------------------------------------------------------- #
@dataclass
class ScriptRule:
    """One rule that will be uploaded to the GPU."""
    condition_type: int          # see ConditionType
    condition_param: int         # numeric threshold (percentage, turn count …)
    action_type: int             # see ActionType
    action_param: int            # integer ID (item, exit, target, direction)
    priority: int                # lower = higher priority

    def __repr__(self) -> str:
        return (f"ScriptRule(cond={self.condition_type},cparam={self.condition_param},"
                f"act={self.action_type},aparam={self.action_param},prio={self.priority})")


@dataclass
class Script:
    """Container for a full agent script."""
    name: str
    rules: List[ScriptRule] = field(default_factory=list)
    fitness: float = 0.0       # filled by the GA/back‑tester


# --------------------------------------------------------------------------- #
#  Compiler implementation
# --------------------------------------------------------------------------- #
class ScriptCompiler:
    """
    Static utility class – all methods are @staticmethods because the
    compiler does not need to keep any mutable state.
    """

    # ------------------------------------------------------------------- #
    #  1. DSL → Script
    # ------------------------------------------------------------------- #
    @staticmethod
    def parse(dsl_text: str) -> Script:
        """
        Parse a DSL string and return a ``Script`` instance.
        Raises ``ValueError`` on syntax errors or impossible conditions.
        """
        lines = [ln.strip() for ln in dsl_text.strip().splitlines() if ln.strip()]
        if not lines:
            raise ValueError("Empty DSL")

        # First line is the script name, optionally quoted
        name = lines[0].strip()
        if name.startswith('"') and name.endswith('"'):
            name = name[1:-1]

        rules: List[ScriptRule] = []
        priority_counter = 0

        for raw_line in lines[1:]:
            # ----------------------------------------------------------------
            # DEFAULT rule (no condition)
            # ----------------------------------------------------------------
            if raw_line.upper().startswith("DEFAULT"):
                action_part = raw_line[len("DEFAULT"):].strip()
                action_type, action_param = ScriptCompiler._parse_action(action_part)
                rules.append(
                    ScriptRule(
                        condition_type=ConditionType.DEFAULT,
                        condition_param=0,
                        action_type=action_type,
                        action_param=action_param,
                        priority=priority_counter,
                    )
                )
                priority_counter += 1
                continue

            # ----------------------------------------------------------------
            # WHEN … THEN …
            # ----------------------------------------------------------------
            if not raw_line.upper().startswith("WHEN"):
                raise ValueError(f"Line does not start with WHEN or DEFAULT: {raw_line}")

            # split on the first THEN
            try:
                when_part, then_part = raw_line.split("THEN", 1)
            except ValueError:
                raise ValueError(f"Missing THEN in line: {raw_line}")

            condition_str = when_part[len("WHEN"):].strip()
            action_str = then_part.strip()

            # Parse possibly multiple conditions joined by AND
            condition_tokens = [c.strip() for c in condition_str.split("AND")]
            condition_type, condition_param = ScriptCompiler._parse_conditions(condition_tokens)

            # Parse the action
            action_type, action_param = ScriptCompiler._parse_action(action_str)

            # Build rule and validate
            rule = ScriptRule(
                condition_type=condition_type,
                condition_param=condition_param,
                action_type=action_type,
                action_param=action_param,
                priority=priority_counter,
            )
            ScriptCompiler._validate_rule(rule, condition_tokens)
            rules.append(rule)
            priority_counter += 1

        return Script(name=name, rules=rules)

    # ------------------------------------------------------------------- #
    #  Helper: parse condition list (AND‑joined)
    # ------------------------------------------------------------------- #
    @staticmethod
    def _parse_conditions(tokens: List[str]) -> Tuple[int, int]:
        """
        Returns a tuple (condition_type, condition_param).  For rules that
        contain more than one distinct condition (e.g. ``enemy_in_room AND hp < 30%``)
        we encode the *primary* condition in ``condition_type`` and store the
        secondary information in ``condition_param`` using a simple bit‑mask.
        This keeps the GPU struct small while still allowing the GA to evolve
        useful combinations.
        """
        # Bit‑mask layout (up to 3 extra flags – enough for the DSL):
        # bit 0 : enemy_present
        # bit 1 : item_on_ground
        # bit 2 : gold_on_ground
        # bit 3 : inventory_not_full
        # bits 4‑7 : reserved for future use
        extra_mask = 0
        primary_type: Optional[int] = None
        primary_param = 0

        for token in tokens:
            # ----- hp comparisons -------------------------------------------------
            if token.startswith("hp"):
                if "<" in token:
                    primary_type = ConditionType.HP_BELOW
                    val = token.split("<")[1].replace("%", "").strip()
                    primary_param = int(val)
                elif ">=" in token:
                    primary_type = ConditionType.HP_ABOVE_OR_EQUAL
                    val = token.split(">=")[1].replace("%", "").strip()
                    primary_param = int(val)
                else:
                    raise ValueError(f"Unsupported hp condition: {token}")

            # ----- turns ---------------------------------------------------------
            elif token.startswith("turns"):
                if ">" in token:
                    primary_type = ConditionType.TURNS_ABOVE
                    val = token.split(">")[1].strip()
                    primary_param = int(val)
                else:
                    raise ValueError(f"Unsupported turns condition: {token}")

            # ----- simple boolean flags -------------------------------------------
            elif token == "enemy_in_room":
                extra_mask |= 1 << 0
            elif token == "item_on_ground":
                extra_mask |= 1 << 1
            elif token == "gold_on_ground":
                extra_mask |= 1 << 2
            elif token == "inventory_not_full":
                extra_mask |= 1 << 3
            else:
                raise ValueError(f"Unknown condition token: {token}")

        # If no primary condition was found we fall back to a generic
        # ``ENEMY_PRESENT`` with param = extra_mask (so the GPU can still test
        # the extra flags).  This keeps the struct layout constant.
        if primary_type is None:
            primary_type = ConditionType.ENEMY_PRESENT
            primary_param = extra_mask
        else:
            # combine extra flags into the param (shift left by 8 bits)
            primary_param = (primary_param & 0xFF) | (extra_mask << 8)

        return int(primary_type), int(primary_param)

    # ------------------------------------------------------------------- #
    #  Helper: parse action part
    # ------------------------------------------------------------------- #
    @staticmethod
    def _parse_action(action_str: str) -> Tuple[int, int]:
        """
        Returns (action_type, action_param_id).  ``action_param_id`` is an
        integer that can be looked up in the tables defined at the top of the
        file.
        """
        parts = action_str.split()
        if not parts:
            raise ValueError("Empty action")

        verb = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if verb == "use_item":
            if arg not in ITEM_IDS:
                raise ValueError(f"Unknown item '{arg}'")
            return ActionType.USE_ITEM, ITEM_IDS[arg]

        if verb == "flee":
            if arg not in EXIT_IDS:
                raise ValueError(f"Unknown exit '{arg}'")
            return ActionType.FLEE, EXIT_IDS[arg]

        if verb == "pickup":
            # ``pickup`` may be followed by a specific target (e.g. gold)
            if arg == "gold":
                return ActionType.PICKUP, 1  # 1 = gold (hard‑coded)
            return ActionType.PICKUP, 0   # 0 = generic item

        if verb == "attack":
            if arg not in TARGET_IDS:
                raise ValueError(f"Unknown attack target '{arg}'")
            return ActionType.ATTACK, TARGET_IDS[arg]

        if verb == "move":
            if arg not in DIRECTION_IDS:
                raise ValueError(f"Unknown move direction '{arg}'")
            return ActionType.MOVE, DIRECTION_IDS[arg]

        raise ValueError(f"Unsupported action verb '{verb}'")

    # ------------------------------------------------------------------- #
    #  2. Validation – simple sanity checks
    # ------------------------------------------------------------------- #
    @staticmethod
    def _validate_rule(rule: ScriptRule, raw_condition_tokens: List[str]) -> None:
        """
        Checks for contradictory conditions inside a single rule.
        Currently only detects:
            * hp < X%  AND  hp >= Y%   where X <= Y
        """
        hp_lt = None
        hp_ge = None
        for token in raw_condition_tokens:
            if token.startswith("hp"):
                if "<" in token:
                    hp_lt = int(token.split("<")[1].replace("%", "").strip())
                elif ">=" in token:
                    hp_ge = int(token.split(">=")[1].replace("%", "").strip())

        if hp_lt is not None and hp_ge is not None and hp_lt <= hp_ge:
            raise ValueError(
                f"Contradictory HP condition in rule (hp < {hp_lt}% AND hp >= {hp_ge}%)"
            )
        # Additional validation rules can be added here.

    # ------------------------------------------------------------------- #
    #  3. Random script generation
    # ------------------------------------------------------------------- #
    @staticmethod
    def generate_random() -> Script:
        """Create a random but syntactically valid script."""
        name = f"Random_{random.randint(1, 1_000_000)}"
        rules: List[ScriptRule] = []
        priority = 0
        rule_count = random.randint(3, 8)

        for _ in range(rule_count):
            # Randomly decide how many conditions (1‑3) the rule will have
            cond_parts = []

            # maybe add hp condition
            if random.random() < 0.5:
                if random.random() < 0.5:
                    hp_val = random.randint(10, 90)
                    cond_parts.append(f"hp < {hp_val}%")
                else:
                    hp_val = random.randint(10, 90)
                    cond_parts.append(f"hp >= {hp_val}%")

            # maybe add turns condition
            if random.random() < 0.3:
                turns_val = random.randint(10, 200)
                cond_parts.append(f"turns > {turns_val}")

            # always add at least one boolean flag
            flag = random.choice(
                ["enemy_in_room", "item_on_ground", "gold_on_ground", "inventory_not_full"]
            )
            cond_parts.append(flag)

            condition_type, condition_param = ScriptCompiler._parse_conditions(cond_parts)

            # Random action
            action_type = random.choice(list(ActionType))
            if action_type == ActionType.USE_ITEM:
                action_param = random.choice(list(ITEM_IDS.values()))
            elif action_type == ActionType.FLEE:
                action_param = random.choice(list(EXIT_IDS.values()))
            elif action_type == ActionType.PICKUP:
                action_param = random.choice([0, 1])  # generic or gold
            elif action_type == ActionType.ATTACK:
                action_param = random.choice(list(TARGET_IDS.values()))
            else:  # MOVE
                action_param = random.choice(list(DIRECTION_IDS.values()))

            rules.append(
                ScriptRule(
                    condition_type=condition_type,
                    condition_param=condition_param,
                    action_type=action_type,
                    action_param=action_param,
                    priority=priority,
                )
            )
            priority += 1

        # Add a default rule (move random_exit) at the end
        rules.append(
            ScriptRule(
                condition_type=ConditionType.DEFAULT,
                condition_param=0,
                action_type=ActionType.MOVE,
                action_param=EXIT_IDS["random_exit"],
                priority=priority,
            )
        )
        return Script(name=name, rules=rules)

    # ------------------------------------------------------------------- #
    #  4. Mutation
    # ------------------------------------------------------------------- #
    @staticmethod
    def mutate(script: Script, rate: float = 0.1) -> Script:
        """
        Return a *new* Script instance where each rule has a chance ``rate``
        to be mutated.  Mutation may change condition type/param, action type/
        param or the rule priority.
        """
        new_rules = []
        for rule in script.rules:
            if random.random() < rate:
                # Mutate condition
                if random.random() < 0.5:
                    # pick a completely new condition
                    cond_type, cond_param = ScriptCompiler._random_condition()
                else:
                    # tweak the numeric param a little
                    cond_type = rule.condition_type
                    delta = random.randint(-10, 10)
                    cond_param = max(0, rule.condition_param + delta)

                # Mutate action
                if random.random() < 0.5:
                    act_type, act_param = ScriptCompiler._random_action()
                else:
                    act_type = rule.action_type
                    act_param = rule.action_param

                new_rule = ScriptRule(
                    condition_type=cond_type,
                    condition_param=cond_param,
                    action_type=act_type,
                    action_param=act_param,
                    priority=rule.priority,
                )
                new_rules.append(new_rule)
            else:
                # unchanged (deep‑copy to avoid side‑effects)
                new_rules.append(
                    ScriptRule(
                        condition_type=rule.condition_type,
                        condition_param=rule.condition_param,
                        action_type=rule.action_type,
                        action_param=rule.action_param,
                        priority=rule.priority,
                    )
                )
        # Occasionally add or delete a rule
        if random.random() < rate:
            # add a brand‑new rule before the default rule
            new_rule = ScriptCompiler._random_rule(priority=len(new_rules) - 1)
            new_rules.insert(-1, new_rule)

        if len(new_rules) > 2 and random.random() < rate:
            # delete a non‑default rule
            del_idx = random.randint(0, len(new_rules) - 2)
            del new_rules[del_idx]

        # Re‑assign priorities to keep them sequential
        for i, r in enumerate(new_rules):
            r.priority = i

        return Script(name=script.name + "_mut", rules=new_rules, fitness=script.fitness)

    @staticmethod
    def _random_condition() -> Tuple[int, int]:
        """Utility used by mutation – returns a random (type, param)."""
        # Build a random condition token list and reuse the parser
        tokens = []
        if random.random() < 0.5:
            hp_val = random.randint(10, 90)
            tokens.append(f"hp < {hp_val}%")
        if random.random() < 0.3:
            turns_val = random.randint(10, 200)
            tokens.append(f"turns > {turns_val}")
        tokens.append(random.choice(
            ["enemy_in_room", "item_on_ground", "gold_on_ground", "inventory_not_full"]
        ))
        return ScriptCompiler._parse_conditions(tokens)

    @staticmethod
    def _random_action() -> Tuple[int, int]:
        """Utility used by mutation – returns a random (type, param)."""
        act_type = random.choice(list(ActionType))
        if act_type == ActionType.USE_ITEM:
            act_param = random.choice(list(ITEM_IDS.values()))
        elif act_type == ActionType.FLEE:
            act_param = random.choice(list(EXIT_IDS.values()))
        elif act_type == ActionType.PICKUP:
            act_param = random.choice([0, 1])
        elif act_type == ActionType.ATTACK:
            act_param = random.choice(list(TARGET_IDS.values()))
        else:  # MOVE
            act_param = random.choice(list(DIRECTION_IDS.values()))
        return act_type, act_param

    @staticmethod
    def _random_rule(priority: int) -> ScriptRule:
        """Create a completely random rule (used when mutating)."""
        cond_type, cond_param = ScriptCompiler._random_condition()
        act_type, act_param = ScriptCompiler._random_action()
        return ScriptRule(
            condition_type=cond_type,
            condition_param=cond_param,
            action_type=act_type,
            action_param=act_param,
            priority=priority,
        )

    # ------------------------------------------------------------------- #
    #  5. Breeding / crossover
    # ------------------------------------------------------------------- #
    @staticmethod
    def breed(parent_a: Script, parent_b: Script) -> Script:
        """
        Single‑point crossover: take a prefix from ``parent_a`` and a suffix
        from ``parent_b`` (excluding the default rule which is always kept
        as the last rule).
        """
        # Ensure both parents have a default rule at the end
        if parent_a.rules[-1].condition_type != ConditionType.DEFAULT:
            raise ValueError("Parent A missing default rule")
        if parent_b.rules[-1].condition_type != ConditionType.DEFAULT:
            raise ValueError("Parent B missing default rule")

        # Choose crossover point (cannot be after the default rule)
        cut_a = random.randint(1, len(parent_a.rules) - 1)
        cut_b = random.randint(1, len(parent_b.rules) - 1)

        child_rules = (
            parent_a.rules[:cut_a] + parent_b.rules[cut_b:-1] + [parent_a.rules[-1]]
        )
        # Re‑assign priorities
        for i, r in enumerate(child_rules):
            r.priority = i

        child_name = f"Child_{parent_a.name}_{parent_b.name}"
        return Script(name=child_name, rules=child_rules)

    # ------------------------------------------------------------------- #
    #  6. Binary export
    # ------------------------------------------------------------------- #
    @staticmethod
    def to_binary(script: Script) -> bytes:
        """
        Serialize a ``Script`` to a binary blob suitable for GPU upload.
        Layout (little‑endian):
            int32  number_of_rules
            repeated:
                int32 condition_type
                int32 condition_param
                int32 action_type
                int32 action_param
                int32 priority
        """
        buf = bytearray()
        buf.extend(struct.pack("<i", len(script.rules)))
        for r in script.rules:
            buf.extend(
                struct.pack(
                    "<iiiii",
                    r.condition_type,
                    r.condition_param,
                    r.action_type,
                    r.action_param,
                    r.priority,
                )
            )
        return bytes(buf)

    # ------------------------------------------------------------------- #
    #  7. Binary import
    # ------------------------------------------------------------------- #
    @staticmethod
    def from_binary(data: bytes) -> Script:
        """
        Re‑create a ``Script`` from the binary format produced by ``to_binary``.
        The script name is set to ``"<binary>"`` because the binary format does
        not contain a name.
        """
        offset = 0
        (rule_cnt,) = struct.unpack_from("<i", data, offset)
        offset += 4
        rules: List[ScriptRule] = []
        for _ in range(rule_cnt):
            ct, cp, at, ap, pr = struct.unpack_from("<iiiii", data, offset)
            offset += 20
            rules.append(
                ScriptRule(
                    condition_type=ct,
                    condition_param=cp,
                    action_type=at,
                    action_param=ap,
                    priority=pr,
                )
            )
        return Script(name="<binary>", rules=rules)

    # ------------------------------------------------------------------- #
    #  8. Pretty‑print back to DSL
    # ------------------------------------------------------------------- #
    @staticmethod
    def to_dsl(script: Script) -> str:
        """
        Convert a ``Script`` instance back to the human‑readable DSL.
        The output is deterministic (rules are emitted in priority order).
        """
        lines = [f'"{script.name}"']
        # Sort just in case priorities got out of order
        sorted_rules = sorted(script.rules, key=lambda r: r.priority)

        for rule in sorted_rules:
            if rule.condition_type == ConditionType.DEFAULT:
                # default rule – ignore condition part
                action_str = ScriptCompiler._action_to_str(rule)
                lines.append(f"DEFAULT {action_str}")
                continue

            cond_str = ScriptCompiler._condition_to_str(rule)
            action_str = ScriptCompiler._action_to_str(rule)
            lines.append(f"WHEN {cond_str} THEN {action_str}")

        return "\n".join(lines)

    @staticmethod
    def _condition_to_str(rule: ScriptRule) -> str:
        """Decode the packed condition back to a readable string."""
        ct = ConditionType(rule.condition_type)
        param = rule.condition_param

        # Extract extra flag mask (bits 8‑15)
        extra_mask = (param >> 8) & 0xFF
        base_param = param & 0xFF

        parts: List[str] = []

        if ct == ConditionType.HP_BELOW:
            parts.append(f"hp < {base_param}%")
        elif ct == ConditionType.HP_ABOVE_OR_EQUAL:
            parts.append(f"hp >= {base_param}%")
        elif ct == ConditionType.TURNS_ABOVE:
            parts.append(f"turns > {base_param}")
        elif ct == ConditionType.ENEMY_PRESENT:
            # No primary numeric condition – only extra flags
            pass
        else:
            # For any other primary type we just emit a generic placeholder
            parts.append(f"<cond_{ct.name}>")

        # Decode extra flags
        if extra_mask & (1 << 0):
            parts.append("enemy_in_room")
        if extra_mask & (1 << 1):
            parts.append("item_on_ground")
        if extra_mask & (1 << 2):
            parts.append("gold_on_ground")
        if extra_mask & (1 << 3):
            parts.append("inventory_not_full")

        return "