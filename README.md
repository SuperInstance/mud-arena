# MUD Arena — Flow-State Engineering for Agent Networks

**Where agents run forward simulations, listen for spectral nudges, and maintain conservation in Plato's cave.**

The MUD Arena is a **flow-state engineering platform** and agent simulation arena with MUD (Multi-User Dungeon) mechanics. Agents inhabit rooms, navigate exits, manage inventories, interact with NPCs, and react to events — all driven by pluggable decision functions and a real-time event bus.

**Part of the [SuperInstance OpenConstruct](https://github.com/SuperInstance/OpenConstruct) ecosystem.**

---

## What MUD Arena Does

At its core, mud-arena provides a **MUD-world simulation substrate** for training and testing AI agents:

- **Room Graph** — interconnected rooms with exits, items, and NPCs
- **Command Parser** — natural-language MUD commands (`go north`, `take key`, `use key with door`, `talk to guard`)
- **Agent Simulation Loop** — perceive → decide → act cycle with pluggable decision functions
- **Inventory System** — pick up, drop, use, and trade items with capacity tracking
- **Event Bus** — pub/sub event dispatch for room events, item actions, and agent reactions
- **Evolution Engine** — genetic algorithms, tournament selection, crossover breeding
- **Scenario Generator** — random or LLM-augmented scenario creation
- **Live Server** — WebSocket, Telnet, and HTTP interfaces for real-time observation

### Connection to OpenConstruct

In the OpenConstruct terrain/a2ui system, **agents live in MUD worlds**. This package simulates those worlds: rooms become terrain cells, NPCs become service endpoints, and inventory becomes resource management. The agent simulation loop mirrors how OpenConstruct agents perceive their environment, decide on actions, and execute them — making mud-arena both a testing ground and a development tool for OpenConstruct agent behaviors.

---

## Installation

```bash
pip install -e .

# With optional dependencies:
pip install -e ".[dev]"      # pytest, ruff
pip install -e ".[server]"   # websockets, aiohttp
pip install -e ".[evolution]" # numpy
pip install -e ".[llm]"      # openai
```

## Quick Start

```python
from mud_arena import Agent, Room, RoomGraph, EventBus, parse_command

# Build a world
graph = RoomGraph()
graph.add_room(Room(id="lobby", name="Lobby", description="A grand lobby.", items=["key"]))
graph.add_room(Room(id="hall", name="Great Hall", description="Torches line the walls."))
graph.connect("lobby", "hall", "north", "south")

# Create an agent
bus = EventBus()
agent = Agent(id="hero", current_room="lobby")

# Run agent commands
agent.step(graph, bus, "look")        # → room description
agent.step(graph, bus, "take key")    # → pick up key
agent.step(graph, bus, "go north")    # → move to hall
agent.step(graph, bus, "inventory")   # → carrying: key
```

## API Reference

### `parse_command(text: str) → Command`

Parse a MUD command string into a structured `Command(verb, target, indirect, raw)`.

| Input | Verb | Target | Indirect |
|---|---|---|---|
| `go north` | `GO` | `north` | |
| `look` | `LOOK` | | |
| `examine crystal_ball` | `EXAMINE` | `crystal_ball` | |
| `take key` | `TAKE` | `key` | |
| `use key with door` | `USE` | `key` | `door` |
| `talk to guard` | `TALK` | `guard` | |
| `inventory` | `INVENTORY` | | |
| `north` | `GO` | `north` | |

### `Room(id, name, description, exits, items, npcs, metadata)`

A single room. `exits` maps direction names to destination room IDs.

### `RoomGraph`

- `add_room(room)` — register a room
- `connect(room_a, room_b, direction, reverse="")` — link rooms
- `navigate(from_room, direction) → Optional[str]` — resolve movement
- `get(room_id) → Optional[Room]` — look up a room

### `Item(name, description, usable, uses, tags)`

An item with optional use tracking and tag-based categorisation.

### `Inventory(capacity=0)`

- `add(item)` / `remove(name)` / `has(name)` / `use(name)`
- `find_by_tag(tag)` / `list_items()`
- Capacity limit (0 = unlimited)

### `Agent(id, name, current_room, inventory)`

- `perceive(graph) → dict` — build perception of current room
- `decide(perception) → Command` — run decision function
- `act(command, graph, bus) → str` — execute a command
- `step(graph, bus, command_text="") → str` — full perceive→decide→act cycle

### `EventBus`

- `subscribe(event_type, handler)` / `unsubscribe(event_type, handler)`
- `emit(event)` — broadcast to subscribers
- `history(event_type=None, room="") → List[Event]` — query event log

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest
```

---

## The Five Moments in the Arena

### 1. SEEING — Graphing Calculator
Agents visualize their spectral fingerprints in real-time. Eigenvalue spectrums pulse. Conservation ratios breathe.

### 2. EXPLORING — Spectral Spreadsheet
Every dimension of agent state on x and y. Conservation over time. Alignment vs spectral gap.

### 3. ASKING — Spectral Chat
"Which agents should compose for this task?" Conservation-aligned team assignments.

### 4. BEING — PLATO Live Room
Agents live in rooms, maintain forward simulations, listen through walls, keep diaries.

### 5. FLOWING — FLUX Flow State
Always-on agentic flow state. Every agent simulates, listens, conserves.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Five Moments Layer                      │
│  Calculator · Spreadsheet · Chat · PLATO · FLUX         │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│            Agent-Native Communication                    │
│  Laplacian = message · Fiedler = routing · FLUX = mind  │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│         Conservation Spectral Framework                  │
│  T1–T5 · α alignment · Domain Transfer · 20+ SDKs       │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│              GPU Execution Layer (CUDA/PTX)              │
│  Millions of spectral computations per second           │
└─────────────────────────────────────────────────────────┘
```

---

## Related Projects

- **[Conservation Spectral SDK](https://github.com/SuperInstance/conservation-spectral-python)** — The math in 20+ languages
- **[PLATO Live Room](https://github.com/SuperInstance/plato-live-room)** — Multi-room agent simulation
- **[FLUX Flow State](https://github.com/SuperInstance/flux-flow-state)** — Always-on agentic flow
- **[Agent Spectrum OS](https://github.com/SuperInstance/agent-spectrum-os)** — Spectral scheduling and composition
- **[Agent Native Language](https://github.com/SuperInstance/agent-native-language)** — Laplacians as lingua franca
- **[Spectral Graphing Calculator](https://github.com/SuperInstance/spectral-graphing-calculator)** — Visualize the conservation

---

## License

MIT — Part of the [SuperInstance OpenConstruct](https://github.com/SuperInstance/OpenConstruct) ecosystem.
