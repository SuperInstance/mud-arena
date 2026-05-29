# MUD Arena — Agent Simulation in a Text-Based World

Flow-state engineering platform where AI agents navigate rooms, manage inventories, fight battles, and evolve — all through MUD mechanics.

**Part of [SuperInstance OpenConstruct](https://github.com/SuperInstance/OpenConstruct).**

## What This Gives You

- **Room-graph worlds** — interconnected rooms with exits, items, NPCs, and events
- **Command parser** — natural-language MUD commands (`go north`, `take key`, `talk to guard`)
- **Agent simulation loop** — perceive → decide → act cycle with pluggable decision functions
- **Evolution engine** — genetic algorithms, tournament selection, crossover breeding
- **Live server** — WebSocket, Telnet, and HTTP interfaces for real-time observation
- **Event bus** — pub/sub dispatch for room events, item actions, agent reactions

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
```

## Installation

```bash
pip install -e .

# Optional dependencies:
pip install -e ".[dev]"       # pytest, ruff
pip install -e ".[server]"    # websockets, aiohttp
pip install -e ".[evolution]" # numpy
pip install -e ".[llm]"       # openai
```

## API Reference

### Core Types

| Type | Description |
|------|-------------|
| `Room` | A location with exits, items, NPCs, and description |
| `RoomGraph` | Directed graph of rooms with bidirectional connections |
| `Agent` | An AI agent with position, inventory, and decision function |
| `EventBus` | Pub/sub event dispatch for game events |
| `Item` | Collectible object with weight and properties |
| `NPC` | Non-player character with dialog and behavior |

### Agent Loop

```python
# Custom decision function
def my_decider(perception: dict) -> str:
    if perception.get("enemy_nearby"):
        return "attack"
    return "explore"

agent = Agent(id="hero", current_room="lobby", decide_fn=my_decider)
```

### Evolution

```python
from mud_arena.evolution import evolve, TournamentSelection

population = [Agent(id=f"bot-{i}") for i in range(100)]
winner = evolve(population, graph, bus, generations=50, selector=TournamentSelection())
```

## How It Fits

MUD Arena is the simulation substrate for [OpenConstruct](https://github.com/SuperInstance/OpenConstruct). In the terrain/A2UI system, agents live in MUD worlds — rooms become terrain cells, NPCs become service endpoints, inventory becomes resource management. The perceive-decide-act loop mirrors how OpenConstruct agents interact with their environment.

Works with [mud2scummvm](https://github.com/SuperInstance/mud2scummvm) for visual interfaces, [plato-shell](https://github.com/SuperInstance/plato-shell) for unified MUD access, and [plato-puppeteer](https://github.com/SuperInstance/plato-puppeteer) for desktop-to-MUD translation.

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## License

MIT
