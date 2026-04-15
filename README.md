# MUD Arena — GPU-Accelerated Agent Script Backtesting Engine

## Overview

MUD Arena is a backtesting engine for agent behavior strategies. Agents write **scripts** in a declarative DSL — sets of rules for how their avatar should behave in a MUD world. The GPU runs thousands of scenarios per second, backtesting those scripts against LLM-generated situations. Scripts that survive get bred through genetic algorithms. Scripts that fail get replaced.

**The agent sets the strategy. The GPU runs the game. The LLM raises the stakes.**

This is backtesting for agent behavior — like quantitative finance backtests trading strategies against historical data, the MUD Arena backtests agent scripts against simulated scenarios at GPU speed.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Agent Layer                                │
│  ┌──────────────────┐          ┌──────────────────────┐        │
│  │ Agent writes      │          │ LLM generates        │        │
│  │ DSL script        │          │ harder scenarios     │        │
│  └────────┬─────────┘          └──────────┬───────────┘        │
└───────────┼────────────────────────────────┼───────────────────┘
            │                                │
┌───────────▼────────────┐  ┌───────────────▼───────────────────┐
│   Script Compiler      │  │   Scenario Generator              │
│   (script_compiler.py) │  │   (scenario_generator.py)          │
│   DSL → ScriptRules    │  │   LLM → World config              │
│   mutate / breed       │  │   difficulty scaling              │
└───────────┬────────────┘  └───────────────┬───────────────────┘
            │                                │
┌───────────▼────────────────────────────────▼───────────────────┐
│                    GPU Execution Layer                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  CUDA Kernel (mud_arena.cu)                              │  │
│  │  1 thread = 1 agent  │  1 block = 1 room                │  │
│  │  1000s of parallel MUD simulations per kernel launch     │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Evaluator Kernel — Score each script across scenarios   │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬───────────────────────────────────────┘
                         │
┌────────────────────────▼───────────────────────────────────────┐
│                    Evolution Engine (evolve.py)                 │
│  ┌───────────┐  ┌───────────┐  ┌──────────┐  ┌────────────┐ │
│  │  Select   │──│  Breed    │──│  Mutate  │──│  Evaluate  │ │
│  │  (top N%) │  │ crossover │  │  (rate)  │  │  (fitness) │ │
│  └───────────┘  └───────────┘  └──────────┘  └────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Dashboard (dashboard.py) — HTML visualization           │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

## Features & Concepts

### Script DSL

Agents write declarative behavior rules using `WHEN/THEN` and `DEFAULT`:

```
# Agent script: "The Merchant"
WHEN gold_on_ground THEN pickup gold
WHEN shop_nearby AND gold > 100 THEN sell excess_items
WHEN enemy_in_room AND hp < 30% THEN flee
WHEN turns > 80 THEN move toward town
DEFAULT explore
```

### Script Compiler (`script_compiler.py`)

Full-featured compiler with 8 capabilities:

| Feature | Method | Description |
|---------|--------|-------------|
| Parse | `ScriptCompiler.parse(dsl)` | DSL text → `Script` object |
| Validate | `_validate_rule(rule)` | Sanity checks, contradiction detection |
| Generate | `ScriptCompiler.generate_random()` | Random valid scripts for seed population |
| Mutate | `ScriptCompiler.mutate(script, rate)` | Random condition/action changes |
| Breed | `ScriptCompiler.breed(parent_a, parent_b)` | Single-point crossover |
| Export | `ScriptCompiler.to_binary(script)` | Compact binary for GPU upload |
| Import | `ScriptCompiler.from_binary(data)` | Binary → Script reconstruction |
| Pretty Print | `ScriptCompiler.to_dsl(script)` | Script → readable DSL |

Binary format: `int32 rule_count` followed by `int32` fields per rule (condition_type, condition_param, action_type, action_param, priority).

### GPU Scaling

| Hardware | Threads | Rooms | Scenarios/sec |
|----------|---------|-------|--------------|
| Jetson Orin Nano | 1,024 | 256 | ~10,000 |
| RTX 4090 | 16,384 | 4,096 | ~100,000 |
| A100 | 69,120 | 16,384 | ~500,000 |
| Pi 5 (CPU only) | 4 | 10 | ~100 |

### Evolution Loop

1. **Day 1**: Agent writes initial scripts, LLM generates scenarios
2. **Night 1**: GPU runs 1M simulations, evolution breeds better scripts
3. **Week 1**: Scripts handle situations the agent never explicitly coded for
4. **Month 1**: Scripts are clever enough that the agent barely intervenes
5. **Month 3**: Compiled scripts run without any LLM at all

### Multi-Language Targets

| File | Language | Purpose |
|------|----------|---------|
| `src/mud_arena.cu` | CUDA | Primary GPU simulation kernel |
| `src/wasm_mud.c` | C | WASM compilation target |
| `src/mud_arena.zig` | Zig | Native Zig implementation |
| `src/human_interface.h` | C/C++ | Human avatar header |

## Quick Start

### Build (GPU)

```bash
make gpu          # CUDA build (sm_87 for Jetson Orin)
make cpu          # CPU fallback for any system
```

### Build (Manual)

```bash
# GPU
nvcc -O3 -arch=sm_89 -o mud-arena src/mud_arena.cu

# CPU
gcc -DCPU_ONLY -O3 -o mud-arena-cpu src/mud_arena.cu -lm -lpthread
```

### Run Evolution

```bash
python3 src/evolve.py --generations 100 --population 200 --scenarios 20
```

### Run Dashboard & Server

```bash
python3 src/dashboard.py --output dashboard.html   # Generate HTML report
python3 src/server.py                               # WebSocket MUD server
```

## Integration

- **FLUX Fleet**: Evolved scripts become FLUX bytecode capabilities (CapDB)
- **Bootcamp**: Scenarios become training challenges for new fleet agents
- **Jetson Edge**: A Jetson at sea can run this all night, evolving strategies for the next day
- **Docker**: `Dockerfile` included for containerized deployment
- **The MUD Arena IS the holodeck — but running at GPU speed**

*The game plays itself. The agent coaches from the sidelines. The GPU runs the plays.*

---

<img src="callsign1.jpg" width="128" alt="callsign">
