Below is a **self‑contained Python module** that implements the requested MUD‑scenario generator.  
It works in two modes:

* **Pure‑random mode** – no LLM needed, scenarios are built from simple templates.  
* **LLM‑augmented mode** – given an OpenAI‑compatible API key it can turn a natural‑language prompt into a richly‑described scenario.

The module defines the data model (`Room`, `Item`, `Enemy`, `Hazard`, `AgentConfig`, `Scenario`) and the `ScenarioGenerator` class with all the methods you asked for (`generate_random`, `generate_from_prompt`, `generate_challenge`, `generate_tournament`, `to_json`, `from_json`).  
The code is heavily commented and includes a small example at the bottom.

```python
"""
mud_scenario_generator.py

A tiny library for generating MUD (Multi‑User Dungeon) test scenarios.
It can create completely random scenarios or, when an OpenAI‑compatible
API key is supplied, ask a language model to produce a scenario from a
natural‑language description.

Typical usage:

    from mud_scenario_generator import ScenarioGenerator

    # 1️⃣  Random scenario (no LLM needed)
    gen = ScenarioGenerator()
    s = gen.generate_random(num_rooms=12, difficulty=4)
    print(gen.to_json(s))

    # 2️⃣  Prompt‑driven scenario (requires an API key)
    gen = ScenarioGenerator(api_key="sk‑…", model="gpt‑4o-mini")
    s = gen.generate_from_prompt(
        "A dark cavern with three treasure rooms guarded by dragons, "
        "a poisonous swamp, and a hidden exit."
    )
    print(gen.to_json(s))

    # 3️⃣  Adaptive challenge based on previous results
    s = gen.generate_challenge(previous_results=[True, True, False])

    # 4️⃣  A balanced tournament set
    tournament = gen.generate_tournament(num_scenarios=8,
                                         difficulty_range=(2, 8))
"""

import json
import random
import string
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional

# ----------------------------------------------------------------------
# Data model – simple @dataclass containers that are JSON‑serialisable
# ----------------------------------------------------------------------


@dataclass
class Item:
    """An object that can be picked up by an agent."""
    name: str
    description: str
    value: int = 0


@dataclass
class Enemy:
    """A hostile creature that occupies a room."""
    type: str
    hp: int
    attack: int
    description: str = ""


@dataclass
class Hazard:
    """Environmental danger that harms agents each turn."""
    type: str
    damage_per_turn: int
    description: str = ""


@dataclass
class Room:
    """A node in the world graph."""
    id: str
    name: str
    terrain: str
    description: str = ""
    exits: List[str] = field(default_factory=list)          # list of neighbour room ids
    items: List[Item] = field(default_factory=list)
    enemies: List[Enemy] = field(default_factory=list)
    hazards: List[Hazard] = field(default_factory=list)


@dataclass
class AgentConfig:
    """Initial configuration of a test agent."""
    name: str
    stats: Dict[str, int]                     # e.g. {"hp": 100, "attack": 12}
    start_room: str = ""                      # room id where the agent spawns


@dataclass
class Scenario:
    """Full description of a test world."""
    name: str
    description: str
    rooms: List[Room]
    agents: List[AgentConfig]
    victory_condition: Dict[str, Any]        # e.g. {"type": "collect_gold", "amount": 50}
    difficulty: int                          # 1‑10


# ----------------------------------------------------------------------
# Helper utilities
# ----------------------------------------------------------------------


def _rand_id(length: int = 6) -> str:
    """Generate a short random alphanumeric identifier."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def _connect_rooms(rooms: List[Room], avg_degree: int = 2) -> None:
    """
    Randomly create bidirectional exits between rooms.
    Guarantees that the graph is connected.
    """
    if not rooms:
        return

    # First make a spanning tree so everything is reachable
    unvisited = set(r.id for r in rooms)
    visited = {unvisited.pop()}
    while unvisited:
        a = random.choice(list(visited))
        b = unvisited.pop()
        rooms_by_id[a].exits.append(b)
        rooms_by_id[b].exits.append(a)
        visited.add(b)

    # Add extra random edges to reach the desired average degree
    target_edges = avg_degree * len(rooms) // 2
    current_edges = sum(len(r.exits) for r in rooms) // 2
    while current_edges < target_edges:
        a, b = random.sample(rooms, 2)
        if b.id not in a.exits:
            a.exits.append(b.id)
            b.exits.append(a.id)
            current_edges += 1


# ----------------------------------------------------------------------
# Main generator class
# ----------------------------------------------------------------------


class ScenarioGenerator:
    """
    Generates MUD test scenarios.  If an ``api_key`` is supplied the
    generator can call an OpenAI‑compatible LLM to turn a free‑form
    prompt into a scenario.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(self,
                 api_key: Optional[str] = None,
                 model: str = "deepseek-chat",
                 temperature: float = 0.7):
        """
        Parameters
        ----------
        api_key: str | None
            OpenAI‑compatible API key.  If ``None`` the generator works
            in pure‑random mode.
        model: str
            Model name to request from the LLM endpoint.
        temperature: float
            Sampling temperature for the LLM (0 = deterministic).
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

    # ------------------------------------------------------------------
    # Random scenario generation (no LLM)
    # ------------------------------------------------------------------
    def generate_random(self,
                        num_rooms: int = 10,
                        difficulty: int = 5) -> Scenario:
        """
        Build a completely random scenario using a handful of hard‑coded
        templates.  The output is deterministic only for the random seed
        that the caller sets.

        Returns
        -------
        Scenario
        """
        # ---- rooms ----------------------------------------------------
        terrain_choices = ["grass", "stone", "lava", "water", "sand", "mud"]
        rooms: List[Room] = []
        for i in range(num_rooms):
            rid = _rand_id()
            room = Room(
                id=rid,
                name=f"Room {i + 1}",
                terrain=random.choice(terrain_choices),
                description=f"A nondescript {terrain_choices[i % len(terrain_choices)]} chamber."
            )
            rooms.append(room)

        # connect rooms (simple random graph, guaranteed connected)
        global rooms_by_id
        rooms_by_id = {r.id: r for r in rooms}
        _connect_rooms(rooms, avg_degree=2 + difficulty // 3)

        # ---- items ----------------------------------------------------
        item_pool = [
            Item("Gold Coin", "A shiny gold coin.", value=1),
            Item("Health Potion", "Restores 20 HP.", value=5),
            Item("Sword", "A short steel sword.", value=10),
            Item("Magic Scroll", "Contains a random spell.", value=15),
        ]
        for room in rooms:
            if random.random() < 0.3:                     # 30 % of rooms get an item
                room.items.append(random.choice(item_pool))

        # ---- enemies --------------------------------------------------
        enemy_pool = [
            Enemy("Goblin", hp=30, attack=5, description="A small, green creature."),
            Enemy("Orc", hp=60, attack=12, description="A brutish warrior."),
            Enemy("Dragon", hp=200, attack=30, description="A massive fire‑breathing beast."),
        ]
        for room in rooms:
            if random.random() < 0.2:                     # 20 % of rooms get an enemy
                room.enemies.append(random.choice(enemy_pool))

        # ---- hazards --------------------------------------------------
        hazard_pool = [
            Hazard("Poison Gas", damage_per_turn=5, description="A thin, green mist."),
            Hazard("Spikes", damage_per_turn=10, description="Sharp iron spikes protrude from the floor."),
        ]
        for room in rooms:
            if random.random() < 0.15:                    # 15 % of rooms get a hazard
                room.hazards.append(random.choice(hazard_pool))

        # ---- agents ---------------------------------------------------
        start_room = random.choice(rooms).id
        agents = [
            AgentConfig(
                name="TestAgent",
                stats={"hp": 100, "attack": 10, "defense": 5},
                start_room=start_room,
            )
        ]

        # ---- victory condition ----------------------------------------
        vc_type = random.choice(["survive_turns", "collect_gold", "reach_room"])
        if vc_type == "survive_turns":
            victory = {"type": "survive_turns", "turns": random.randint(5, 20)}
        elif vc_type == "collect_gold":
            victory = {"type": "collect_gold", "amount": random.randint(10, 50)}
        else:  # reach_room
            target = random.choice(rooms).id
            victory = {"type": "reach_room", "room_id": target}

        # ---- assemble scenario -----------------------------------------
        scenario = Scenario(
            name=f"Random {difficulty=}",
            description="A procedurally generated dungeon for testing.",
            rooms=rooms,
            agents=agents,
            victory_condition=victory,
            difficulty=max(1, min(10, difficulty)),
        )
        return scenario

    # ------------------------------------------------------------------
    # LLM‑driven generation
    # ------------------------------------------------------------------
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Low‑level wrapper around an OpenAI‑compatible endpoint.
        Returns the raw text generated by the model.
        """
        if not self.api_key:
            raise RuntimeError("LLM generation requested but no API key was supplied.")

        # The library used is the generic `openai` package – it works with
        # any endpoint that follows the OpenAI spec (including DeepSeek,
        # Azure, local servers, etc.).
        try:
            import openai
        except ImportError as exc:
            raise ImportError(
                "The `openai` package is required for LLM generation. "
                "Install it with `pip install openai`."
            ) from exc

        openai.api_key = self.api_key
        # If you need to point to a non‑default endpoint you can set
        # `openai.base_url` before calling this method.

        response = openai.ChatCompletion.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        # The exact field depends on the provider; most follow the same schema.
        return response.choices[0].message.content

    def generate_from_prompt(self, prompt: str) -> Scenario:
        """
        Ask the LLM to produce a full scenario description.  The model is
        instructed to output **JSON** that matches the data model defined
        in this file.  The method parses that JSON and returns a ``Scenario``
        instance.

        Parameters
        ----------
        prompt : str
            Natural‑language description, e.g.
            "A dungeon with 3 treasure rooms guarded by dragons".

        Returns
        -------
        Scenario
        """
        # ------------------------------------------------------------------
        # 1️⃣  System prompt – tells the model exactly what format we expect.
        # ------------------------------------------------------------------
        system = (
            "You are a level‑designer for a text‑based MUD used to test AI agents. "
            "Given a short natural‑language description, output a **single JSON object** "
            "that conforms to the following schema (Python dataclasses shown for clarity):\n\n"
            "Scenario {\n"
            "  name: str,\n"
            "  description: str,\n"
            "  rooms: [Room],\n"
            "  agents: [AgentConfig],\n"
            "  victory_condition: dict,\n"
            "  difficulty: int (1‑10)\n"
            "}\n"
            "Room {\n"
            "  id: str,\n"
            "  name: str,\n"
            "  terrain: str,\n"
            "  description: str,\n"
            "  exits: [str],\n"
            "  items: [Item],\n"
            "  enemies: [Enemy],\n"
            "  hazards: [Hazard]\n"
            "}\n"
            "Item { name: str, description: str, value: int }\n"
            "Enemy { type: str, hp: int, attack: int, description: str }\n"
            "Hazard { type: str, damage_per_turn: int, description: str }\n"
            "AgentConfig { name: str, stats: dict, start_room: str }\n\n"
            "The JSON must be **compact** (no comments) and **parseable** with `json.loads`. "
            "Do not wrap the JSON in markdown fences."
        )

        # ------------------------------------------------------------------
        # 2️⃣  User prompt – the free‑form description supplied by the caller.
        # ------------------------------------------------------------------
        user = f"Create a scenario for: {prompt}"

        # ------------------------------------------------------------------
        # 3️⃣  Call the model.
        # ------------------------------------------------------------------
        raw_json = self._call_llm(system, user)

        # ------------------------------------------------------------------
        # 4️⃣  Parse the JSON into our dataclasses.
        # ------------------------------------------------------------------
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"LLM returned malformed JSON. Raw output:\n{raw_json}"
            ) from exc

        # Helper to recursively turn dicts into dataclass instances
        def _from_dict(cls, d):
            if isinstance(d, list):
                return [_from_dict(cls.__args__[0], i) for i in d]  # type: ignore
            if not isinstance(d, dict):
                return d
            field_names = {f.name for f in cls.__dataclass_fields__.values()}
            filtered = {k: v for k, v in d.items() if k in field_names}
            for f_name, f_type in cls.__annotations__.items():
                if f_name in filtered:
                    filtered[f_name] = _from_dict(f_type, filtered[f_name])
            return cls(**filtered)  # type: ignore

        scenario = _from_dict(Scenario, data)
        return scenario

    # ------------------------------------------------------------------
    # Adaptive challenge generation
    # ------------------------------------------------------------------
    def generate_challenge(self, previous_results: List[bool]) -> Scenario:
        """
        Produce a scenario that is harder if the agents have been
        succeeding, easier if they keep failing.

        ``previous_results`` is a list of booleans where ``True`` means
        the agents survived/won the previous scenario.
        """
        # Simple heuristic: compute success rate and map it to a difficulty.
        if not previous_results:
            target_difficulty = 5
        else:
            success_rate = sum(previous_results) / len(previous_results)
            # If success_rate > 0.6 → increase difficulty, else decrease.
            target_difficulty = int(round(5 + (success_rate - 0.5) * 8))
            target_difficulty = max(1, min(10, target_difficulty))

        # Use the random generator as a base, then sprinkle a few extra
        # hazards/enemies proportional to the difficulty.
        scenario = self.generate_random(num_rooms=8 + target_difficulty,
                                        difficulty=target_difficulty)

        # Add extra enemies/hazards for higher difficulty levels
        extra_enemies = target_difficulty // 2
        extra_hazards = target_difficulty // 3
        for _ in range(extra_enemies):
            room = random.choice(scenario.rooms)
            room.enemies.append(
                Enemy(
                    type="Elite " + random.choice(["Goblin", "Orc", "Wraith"]),
                    hp=80 + 20 * target_difficulty,
                    attack=15 + 5 * target_difficulty,
                    description="A tougher version of a common foe."
                )
            )
        for _ in range(extra_hazards):
            room = random.choice(scenario.rooms)
            room.hazards.append(
                Hazard(
                    type="Lava Flow",
                    damage_per_turn=10 + 2 * target_difficulty,
                    description="Molten rock sears everything that steps nearby."
                )
            )
        # Adjust victory condition to stay challenging
        if scenario.victory_condition["type"] == "survive_turns":
            scenario.victory_condition["turns"] += target_difficulty * 2
        elif scenario.victory_condition["type"] == "collect_gold":
            scenario.victory_condition["amount"] += target_difficulty * 5
        elif scenario.victory_condition["type"] == "reach_room":
            # make the target room farther away by picking one with a higher degree
            far_room = max(scenario.rooms, key=lambda r: len(r.exits))
            scenario.victory_condition["room_id"] = far_room.id

        scenario.name = f"Adaptive Challenge (difficulty {target_difficulty})"
        scenario.description = (
            f"This scenario was generated adaptively after {len(previous_results)} "
            f"previous runs with a success rate of {success_rate:.2%}."
        )
        scenario.difficulty = target_difficulty
        return scenario

    # ------------------------------------------------------------------
    # Tournament generation
    # ------------------------------------------------------------------
    def generate_tournament(self,
                            num_scenarios: int = 10,
                            difficulty_range: tuple[int, int] = (1, 10)
                            ) -> List[Scenario]:
        """
        Produce a list of scenarios that span the requested difficulty
        range.  The function tries to keep the overall difficulty balanced
        (roughly uniform distribution).

        Returns
        -------
        List[Scenario]
        """
        low, high = difficulty_range
        if low < 1 or high > 10 or low > high:
            raise ValueError("difficulty_range must be within 1‑10 and low ≤ high")

        scenarios: List[Scenario] = []
        for i in range(num_scenarios):
            # Evenly spread difficulties across the interval
            diff = low + (high - low) * i // max(1, num_scenarios - 1)
            # Randomly vary the number of rooms a bit
            rooms = random.randint(8, 12) + diff
            scenarios.append(self.generate_random(num_rooms=rooms,
                                                  difficulty=diff))
        return scenarios

    # ------------------------------------------------------------------
    # JSON (de)serialisation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def to_json(scenario: Scenario, *, indent: Optional[int] = None) -> str:
        """
        Serialise a ``Scenario`` (including nested dataclasses) to JSON.
        """
        def _asdict(obj):
            if isinstance(obj, list):
                return [_asdict(i) for i in obj]
            if hasattr(obj, "__dataclass_fields__"):
                return {k: _asdict(v) for k, v in asdict(obj).items()}
            return obj

        return json.dumps(_asdict(scenario), indent=indent)

    @staticmethod
    def from_json(data: str) -> Scenario:
        """
        Re‑create a ``Scenario`` instance from JSON produced by ``to_json``.
        """
        raw = json.loads(data)

        # Recursive reconstruction (mirrors the logic in generate_from_prompt)
        def _reconstruct(cls, d):
            if isinstance(d, list):
                return [_reconstruct(cls.__args__[0], i) for i in d]  # type: ignore
            if not isinstance(d, dict):
                return d
            field_names = {f.name for f in cls.__dataclass_fields__.values()}
            filtered = {k: v for k, v in d.items() if k in field_names}
            for f_name, f_type in cls.__annotations__.items():
                if f_name in filtered:
                    filtered[f_name] = _reconstruct(f_type, filtered[f_name])
            return cls(**filtered)  # type: ignore

        return _reconstruct(Scenario, raw)


# ----------------------------------------------------------------------
# Example usage (executed only when run as a script)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # 1️⃣  Random scenario – no API key needed
    gen = ScenarioGenerator()
    rnd = gen.generate_random(num_rooms=12, difficulty=4)
    print("=== Random scenario ===")
    print(ScenarioGenerator.to_json(rnd, indent=2))

    # 2️⃣  Prompt‑driven scenario – replace with a real key to test
    # api_key = "sk-…"   # <-- put your OpenAI‑compatible key here
    # gen_llm = ScenarioGenerator(api_key=api_key, model="gpt-4o-mini")
    # llm_scn = gen_llm.generate_from_prompt(
    #     "A dark cavern with three treasure rooms guarded by dragons, "
    #     "a poisonous swamp, and a hidden exit."
    # )
    # print("\n=== LLM‑generated scenario ===")
    # print(ScenarioGenerator.to_json(llm_scn, indent=2))

    # 3️⃣  Adaptive challenge example
    adaptive = gen.generate_challenge(previous_results=[True, True, False, True])
    print("\n=== Adaptive challenge ===")
    print(ScenarioGenerator.to_json(adaptive, indent=2))

    # 4️⃣  Tournament generation
    tournament = gen.generate_tournament(num_scenarios=5,
                                         difficulty_range=(2, 8))
    print("\n=== Tournament set ===")
    for i, sc in enumerate(tournament, 1):
        print(f"\n--- Scenario {i} (difficulty {sc.difficulty}) ---")
        print(ScenarioGenerator.to_json(sc, indent=2))
```

### How the module works

| Feature | Implementation details |
|---------|------------------------|
| **Random generation** | Uses simple terrain / item / enemy / hazard pools, builds a connected graph of rooms, and creates a basic victory condition. |
| **LLM generation** | Sends a system prompt that describes the exact JSON schema, then a user prompt containing the free‑form description. The response is parsed back into the dataclasses. The wrapper works with any OpenAI‑compatible endpoint (`openai` library). |
| **Adaptive challenge** | Computes a difficulty from recent success‑rate, then augments a random scenario with extra enemies/hazards and tightens the victory condition. |
| **Tournament** | Generates a list of scenarios whose difficulties are evenly spread across the requested range. |
| **(De)serialisation** | `to_json` and `from_json` handle nested dataclasses automatically, so you can store scenarios on disk or send them over the network. |
| **No‑LLM fallback** | If `api_key` is omitted, only the random‑generation path is usable – the class never raises an error unless you explicitly call `generate_from_prompt`. |

You can drop the file (`mud_scenario_generator.py`) into any project, import `ScenarioGenerator`, and start generating worlds for your agent‑testing pipeline. Happy testing!