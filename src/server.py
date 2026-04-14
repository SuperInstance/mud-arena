Below is a **complete, self‑contained Python module** that implements the MUD‑watch server you described.  
It uses only the standard library (`asyncio`, `json`, `subprocess`, …) together with two very lightweight third‑party packages:

* **`websockets`** – for the WebSocket endpoint (port 7779)  
* **`aiohttp`** – for the REST/HTTP API (port 7780)

Both packages are pure‑Python and work on any recent Python 3.9+ interpreter.  
If you do not already have them, install with:

```bash
pip install websockets aiohttp
```

---

## How the code is organised

| Component | What it does | Key functions / classes |
|-----------|--------------|--------------------------|
| **Simulation driver** | Reads the live output of the GPU‑based simulator (or falls back to a tiny CPU‑only dummy simulator) and pushes updates into a central `World` object. | `SimulationRunner`, `CPUFallbackSimulator` |
| **World model** | Holds the current state of rooms, agents, scores, generation stats and scenarios. Provides async notification to any number of “watchers”. | `World` |
| **WebSocket server** | Accepts connections on **7779**. After a simple login the client can issue the read‑only commands (`look`, `map`, …) and can `watch <agent_id>` to receive a live stream of that agent’s actions. | `websocket_handler` |
| **Telnet server** | Mirrors the same command set on **7778** using plain TCP sockets, so existing Holodeck clients keep working. | `telnet_handler` |
| **HTTP API** | Exposes the read‑only data via the REST endpoints you listed on **7780**. | `status_handler`, `agents_handler`, … |
| **Main entry point** | Starts the three servers and the simulation driver concurrently. | `main()` |

The design is deliberately **event‑driven**: every time the simulation produces a new “tick” the `World` object updates its internal structures and notifies all registered watchers (WebSocket or Telnet clients that asked to `watch` a particular agent).  This gives you true real‑time visibility without any polling loops on the client side.

---

## The full module

```python
#!/usr/bin/env python3
"""
MUD‑watch server – lets humans observe AI agents playing in real time.

Features
--------
* WebSocket endpoint   : ws://<host>:7779
* Telnet endpoint      : <host>:7778
* HTTP/REST API        : http://<host>:7780
* Reads live output from a GPU‑based simulator; if no GPU is present a tiny
  CPU‑only fallback simulator runs instead.
* All commands are **read‑only** – humans can watch but cannot control agents.

Author  : ChatGPT (2024‑06‑14)
License : MIT
"""

import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import websockets
from aiohttp import web

# ----------------------------------------------------------------------
# Configuration (ports, paths, etc.)
# ----------------------------------------------------------------------
WEBSOCKET_PORT = 7779
TELNET_PORT = 7778
HTTP_PORT = 7780

# Path to the external GPU‑based simulator binary (if any).  The binary is
# expected to write newline‑delimited JSON objects to stdout, each object
# representing a simulation tick.
GPU_SIM_BINARY = Path("./gpu_simulator")   # <-- change to your real binary

# ----------------------------------------------------------------------
# Data model – the shared “world” state
# ----------------------------------------------------------------------
@dataclass
class AgentState:
    """Minimal representation of an agent that is useful for watching."""
    id: str
    name: str
    location: str
    last_action: str = ""
    score: float = 0.0
    # you can extend this with more fields (health, inventory, …)

@dataclass
class World:
    """Thread‑safe container for the whole simulation state."""
    rooms: Dict[str, Dict[str, Any]] = field(default_factory=dict)          # room_id → room data
    agents: Dict[str, AgentState] = field(default_factory=dict)           # agent_id → state
    scores: Dict[str, float] = field(default_factory=dict)                # script_id → score
    generation: Dict[str, Any] = field(default_factory=dict)              # evolution stats
    scenarios: List[Dict[str, Any]] = field(default_factory=list)         # active scenarios

    # Watchers: mapping from agent_id → set of async callbacks (WebSocket/Telnet)
    _watchers: Dict[str, Set[asyncio.Queue]] = field(default_factory=lambda: defaultdict(set))
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # ------------------------------------------------------------------
    # Public API – called by the simulation driver
    # ------------------------------------------------------------------
    async def update_from_tick(self, tick: Dict[str, Any]) -> None:
        """
        Apply a single simulation tick (a dict parsed from JSON) to the world.
        The exact schema of the tick is up to the simulator; we support a
        minimal subset that matches the commands we expose.
        """
        async with self._lock:
            # 1️⃣ Update rooms (optional)
            if "rooms" in tick:
                self.rooms.update(tick["rooms"])

            # 2️⃣ Update agents
            if "agents" in tick:
                for aid, ainfo in tick["agents"].items():
                    agent = self.agents.get(aid)
                    if agent is None:
                        agent = AgentState(
                            id=aid,
                            name=ainfo.get("name", f"Agent-{aid}"),
                            location=ainfo.get("location", "unknown"),
                        )
                        self.agents[aid] = agent
                    # mutate fields
                    agent.location = ainfo.get("location", agent.location)
                    agent.last_action = ainfo.get("action", agent.last_action)
                    agent.score = ainfo.get("score", agent.score)

                    # Notify any watchers of this agent
                    await self._notify_watchers(aid, {
                        "type": "agent_update",
                        "agent_id": aid,
                        "location": agent.location,
                        "action": agent.last_action,
                        "score": agent.score,
                    })

            # 3️⃣ Update scores (script‑level)
            if "scores" in tick:
                self.scores.update(tick["scores"])

            # 4️⃣ Update generation stats
            if "generation" in tick:
                self.generation.update(tick["generation"])

            # 5️⃣ Update scenarios
            if "scenarios" in tick:
                self.scenarios = tick["scenarios"]

    # ------------------------------------------------------------------
    # Watcher management
    # ------------------------------------------------------------------
    async def register_watcher(self, agent_id: str, queue: asyncio.Queue) -> None:
        """Add a queue that will receive JSON‑serialisable messages for *agent_id*."""
        async with self._lock:
            self._watchers[agent_id].add(queue)

    async def unregister_watcher(self, agent_id: str, queue: asyncio.Queue) -> None:
        """Remove a previously‑registered queue."""
        async with self._lock:
            self._watchers[agent_id].discard(queue)
            if not self._watchers[agent_id]:
                del self._watchers[agent_id]

    async def _notify_watchers(self, agent_id: str, payload: Dict[str, Any]) -> None:
        """Push *payload* to every queue watching *agent_id*."""
        # NOTE: we deliberately do NOT hold the lock while we put() into queues,
        # because a slow consumer could block the whole world update.
        queues = list(self._watchers.get(agent_id, []))
        for q in queues:
            # `put_nowait` is safe because the queue size is bounded (default 0 → infinite)
            q.put_nowait(payload)

    # ------------------------------------------------------------------
    # Snapshot helpers for the various protocols
    # ------------------------------------------------------------------
    async def snapshot(self) -> Dict[str, Any]:
        """Return a deep copy of the whole world (used by HTTP API)."""
        async with self._lock:
            return {
                "rooms": self.rooms,
                "agents": {aid: vars(a) for aid, a in self.agents.items()},
                "scores": self.scores,
                "generation": self.generation,
                "scenarios": self.scenarios,
            }

    async def agent_list(self) -> List[Dict[str, Any]]:
        async with self._lock:
            return [{"id": a.id, "name": a.name, "location": a.location,
                     "score": a.score, "last_action": a.last_action}
                    for a in self.agents.values()]

    async def room_graph(self) -> Dict[str, Any]:
        async with self._lock:
            return self.rooms

    async def script_scores(self) -> Dict[str, float]:
        async with self._lock:
            return self.scores

    async def generation_stats(self) -> Dict[str, Any]:
        async with self._lock:
            return self.generation

    async def scenario_list(self) -> List[Dict[str, Any]]:
        async with self._lock:
            return self.scenarios


# ----------------------------------------------------------------------
# Simulation runner – reads from GPU binary or falls back to CPU dummy
# ----------------------------------------------------------------------
class SimulationRunner:
    """
    Starts the external GPU simulator (if present) and forwards each JSON line
    to the shared ``World`` instance.  If the binary cannot be started, a very
    small CPU‑only dummy simulator runs instead.
    """
    def __init__(self, world: World):
        self.world = world
        self._process: asyncio.subprocess.Process | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if GPU_SIM_BINARY.is_file() and os.access(GPU_SIM_BINARY, os.X_OK):
            await self._start_gpu()
        else:
            await self._start_cpu_fallback()

    async def _start_gpu(self) -> None:
        """Launch the external binary and read its stdout line‑by‑line."""
        self._process = await asyncio.create_subprocess_exec(
            str(GPU_SIM_BINARY),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert self._process.stdout is not None  # for mypy
        self._task = asyncio.create_task(self._read_stdout(self._process.stdout))
        # Also forward stderr to our own log (helps debugging)
        asyncio.create_task(self._forward_stderr(self._process.stderr))

    async def _forward_stderr(self, stream: asyncio.StreamReader | None) -> None:
        if stream is None:
            return
        async for line in stream:
            sys.stderr.buffer.write(line)
            sys.stderr.flush()

    async def _read_stdout(self, stream: asyncio.StreamReader) -> None:
        """Consume newline‑delimited JSON from the simulator."""
        async for raw in stream:
            line = raw.decode().strip()
            if not line:
                continue
            try:
                tick = json.loads(line)
                await self.world.update_from_tick(tick)
            except json.JSONDecodeError:
                print(f"[SIM] Invalid JSON: {line!r}", file=sys.stderr)

    async def _start_cpu_fallback(self) -> None:
        """A tiny deterministic simulator that produces synthetic ticks."""
        print("[SIM] GPU binary not found – starting CPU fallback simulator.")
        self._task = asyncio.create_task(CPUFallbackSimulator(self.world).run())

    async def stop(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.terminate()
            await self._process.wait()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


class CPUFallbackSimulator:
    """
    Very small deterministic “simulation” that creates a few rooms and agents
    and moves the agents around every second.  It is *only* meant as a placeholder
    when no real GPU simulator is available.
    """
    def __init__(self, world: World):
        self.world = world
        self._rooms = ["room_a", "room_b", "room_c"]
        self._agents = ["alpha", "beta", "gamma"]
        self._tick = 0

    async def run(self) -> None:
        # Initialise static world data once
        await self.world.update_from_tick({
            "rooms": {
                "room_a": {"desc": "A bright, empty chamber."},
                "room_b": {"desc": "A dimly lit corridor."},
                "room_c": {"desc": "A mysterious cavern."},
            },
            "agents": {
                aid: {"name": f"CPU-{aid}", "location": self._rooms[0], "score": 0}
                for aid in self._agents
            },
            "scores": {aid: 0 for aid in self._agents},
            "generation": {"epoch": 0, "population": len(self._agents)},
            "scenarios": [{"id": "demo", "description": "CPU demo scenario"}],
        })

        while True:
            await asyncio.sleep(1.0)          # one tick per second
            self._tick += 1

            # Move each agent to the next room (cyclic)
            agents_update = {}
            for aid in self._agents:
                cur_loc = self.world.agents[aid].location
                nxt_idx = (self._rooms.index(cur_loc) + 1) % len(self._rooms)
                nxt_loc = self._rooms[nxt_idx]
                agents_update[aid] = {
                    "location": nxt_loc,
                    "action": f"move to {nxt_loc}",
                    "score": self.world.agents[aid].score + 1,
                }

            await self.world.update_from_tick({
                "agents": agents_update,
                "scores": {aid: self.world.agents[aid].score for aid in self._agents},
                "generation": {"epoch": self._tick // 10, "population": len(self._agents)},
            })


# ----------------------------------------------------------------------
# Helper – simple command parser (shared by WS & Telnet)
# ----------------------------------------------------------------------
def parse_command(line: str) -> Tuple[str, List[str]]:
    """Return (cmd, args) where cmd is lower‑cased."""
    parts = line.strip().split()
    if not parts:
        return "", []
    return parts[0].lower(), parts[1:]


# ----------------------------------------------------------------------
# WebSocket server (port 7779)
# ----------------------------------------------------------------------
async def websocket_handler(websocket: websockets.WebSocketServerProtocol, path: str, world: World):
    """
    One client per connection.  After login the client can issue any of the
    read‑only commands.  If the client issues ``watch <agent_id>`` we start
    forwarding live updates for that agent until the client sends another
    ``watch`` command or disconnects.
    """
    # Simple greeting – you can replace with a proper auth handshake if you wish
    await websocket.send(json.dumps({"msg": "Welcome to the MUD‑watch server"}))

    # Each client can have at most one active watch at a time.
    watch_queue: asyncio.Queue | None = None
    watched_agent: str | None = None

    async def forward_watcher():
        """Background task that pulls from the queue and pushes to the WS."""
        assert watch_queue is not None
        while True:
            payload = await watch_queue.get()
            await websocket.send(json.dumps(payload))

    forward_task: asyncio.Task | None = None

    try:
        async for raw_msg in websocket:
            line = raw_msg.strip()
            if not line:
                continue
            cmd, args = parse_command(line)

            # ------------------------------------------------------------------
            # 1️⃣  Simple one‑shot commands (no persistent state)
            # ------------------------------------------------------------------
            if cmd == "look":
                # For demo purposes we just echo the location of the first agent.
                async with world._lock:
                    if world.agents:
                        first = next(iter(world.agents.values()))
                        await websocket.send(json.dumps({
                            "type": "look",
                            "room": first.location,
                            "description": world.rooms.get(first.location, {}).get("desc", "")
                        }))
                    else:
                        await websocket.send(json.dumps({"type": "look", "msg": "No agents yet"}))

            elif cmd == "map":
                await websocket.send(json.dumps({
                    "type": "map",
                    "rooms": await world.room_graph()
                }))

            elif cmd == "agents":
                await websocket.send(json.dumps({
                    "type": "agents",
                    "list": await world.agent_list()
                }))

            elif cmd == "scores":
                await websocket.send(json.dumps({
                    "type": "scores",
                    "scores": await world.script_scores()
                }))

            elif cmd == "leaderboard":
                # Very simple leaderboard – top‑N by score
                agents = await world.agent_list()
                top = sorted(agents, key=lambda a: a["score"], reverse=True)[:10]
                await websocket.send(json.dumps({
                    "type": "leaderboard",
                    "top": top
                }))

            elif cmd == "generation":
                await websocket.send(json.dumps({
                    "type": "generation",
                    "stats": await world.generation_stats()
                }))

            elif cmd == "scenarios":
                await websocket.send(json.dumps({
                    "type": "scenarios",
                    "list": await world.scenario_list()
                }))

            # ------------------------------------------------------------------
            # 2️⃣  Watch command – set up a live feed for a specific agent
            # ------------------------------------------------------------------
            elif cmd == "watch":
                if not args:
                    await websocket.send(json.dumps({"error": "watch requires an agent id"}))
                    continue
                agent_id = args[0]

                # Clean up any previous watch
                if watch_queue and watched_agent:
                    await world.unregister_watcher(watched_agent, watch_queue)
                    if forward_task:
                        forward_task.cancel()
                        try:
                            await forward_task
                        except asyncio.CancelledError:
                            pass

                # Verify the agent exists
                async with world._lock:
                    if agent_id not in world.agents:
                        await websocket.send(json.dumps({"error": f"unknown agent {agent_id}"}))
                        watch_queue = None
                        watched_agent = None
                        continue

                # Create a new queue and register it
                watch_queue = asyncio.Queue()
                watched_agent = agent_id
                await world.register_watcher(agent_id, watch_queue)

                # Send an immediate snapshot of the current state
                agent = world.agents[agent_id]
                await websocket.send(json.dumps({
                    "type": "watch_start",
                    "agent_id": agent_id,
                    "location": agent.location,
                    "action": agent.last_action,
                    "score": agent.score,
                }))

                # Start background forwarder
                forward_task = asyncio.create_task(forward_watcher())

            else:
                await websocket.send(json.dumps({"error": f"unknown command {cmd}"}))

    except websockets.ConnectionClosed:
        pass
    finally:
        # Clean up any watch registration when the client disconnects
        if watch_queue and watched_agent:
            await world.unregister_watcher(watched_agent, watch_queue)
        if forward_task:
            forward_task.cancel()
            try:
                await forward_task
            except asyncio.CancelledError:
                pass


async def start_websocket_server(world: World):
    async def handler(ws, path):
        await websocket_handler(ws, path, world)

    server = await websockets.serve(handler, host="0.0.0.0", port=WEBSOCKET_PORT)
    print(f"[WS] Listening on 0.0.0.0:{WEBSOCKET_PORT}")
    await server.wait_closed()


# ----------------------------------------------------------------------
# Telnet server (port 7778) – plain TCP, line‑oriented
# ----------------------------------------------------------------------
async def telnet_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, world: World):
    """
    Mirrors the same command set as the WebSocket server.  The telnet client
    receives a textual response for each command.  For ``watch`` we push a
    line of JSON for every agent update.
    """
    peer = writer.get_extra_info("peername")
    print(f"[TELNET] Connection from {peer}")

    # Greet the client
    writer.write(b"Welcome to the MUD‑watch telnet interface\r\n")
    await writer.drain()

    watch_queue: asyncio.Queue | None = None
    watched_agent: str | None = None
    forward_task: asyncio.Task | None = None

    async def forward_watcher():
        assert watch_queue is not None
        while True:
            payload = await watch_queue.get()
            line = json.dumps(payload) + "\r\n"
            writer.write(line.encode())
            await writer.drain()

    try:
        while not reader.at_eof():
            writer.write(b"> ")
            await writer.drain()
            raw = await reader.readline()
            if not raw:
                break
            line = raw.decode().strip()
            if not line:
                continue
            cmd, args = parse_command(line)

            # ------------------------------------------------------------------
            # One‑shot commands (textual output)
            # ------------------------------------------------------------------
            if cmd == "look":
                async with world._lock:
                    if world.agents:
                        first = next(iter(world.agents.values()))
                        desc = world.rooms.get(first.location, {}).get("desc", "")
                        writer.write(f"You are in {first.location}: {desc}\r\n".encode())
                    else:
                        writer.write(b"No agents in the world yet.\r\n")
                await writer.drain()

            elif cmd == "map":
                rooms = await world.room_graph()
                writer.write((json.dumps(rooms, indent=2) + "\r\n").encode())
                await writer.drain()

            elif cmd == "agents":
                lst = await world.agent_list()
                writer.write((json.dumps(lst, indent=2) + "\r\n").encode())
                await writer.drain()

            elif cmd == "scores":
                scr = await world.script_scores()
                writer.write((json.dumps(scr, indent=2) + "\r\n").encode())
                await writer.drain()

            elif cmd == "leaderboard":
                agents = await world.agent_list()
                top = sorted(agents, key=lambda a: a["score"], reverse=True)[:10]
                writer.write((json.dumps(top, indent=2) + "\r\n").encode())
                await writer.drain()

            elif cmd == "generation":
                gen = await world.generation_stats()
                writer.write((json.dumps(gen, indent=2) + "\r\n").encode())
                await writer.drain()

            elif cmd == "scenarios":
                sc = await world.scenario_list()
                writer.write((json.dumps(sc, indent=2) + "\r\n").encode())
                await writer.drain()

            # ------------------------------------------------------------------
            # Watch command – live JSON feed
            # ------------------------------------------------------------------
            elif cmd == "watch":
                if not args:
                    writer.write(b"watch requires an agent id\r\n")
                    await writer.drain()
                    continue
                agent_id = args[0]

                # Clean up previous watch
                if watch_queue and watched_agent:
                    await world.unregister_watcher(watched_agent, watch_queue)
                    if forward_task:
                        forward_task.cancel()
                        try:
                            await forward_task
                        except asyncio.CancelledError:
                            pass

                async with world._lock:
                    if agent_id not in world.agents:
                        writer.write(f"unknown agent {agent_id}\r\n".encode())
                        await writer.drain()
                        watch_queue = None
                        watched_agent = None
                        continue

                watch_queue = asyncio.Queue()
                watched_agent = agent_id
                await world.register_watcher(agent_id, watch_queue)

                # Immediate snapshot
                a = world.agents[agent_id]
                writer.write(json.dumps({
                    "type": "watch_start",
                    "agent_id": agent_id,
                    "location": a.location,
                    "action": a.last_action,
                    "score": a.score,
                }).encode() + b"\r\n")
                await writer.drain()

                forward_task = asyncio.create_task(forward_watcher())

            else:
                writer.write(f"unknown command: {cmd}\r\n".encode())
                await writer.drain()

    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass
    finally:
        if watch_queue and watched_agent:
            await world.unregister_watcher(watched_agent, watch_queue)
        if forward_task:
            forward_task.cancel()
            try:
                await forward_task
            except asyncio.CancelledError:
                pass
        writer.close()
        await writer.wait_closed()
        print(f"[TELNET] Disconnected {peer}")


async def start_telnet_server(world: World):
    server = await asyncio.start_server(
        lambda r, w: telnet_handler(r, w, world),
        host="0.0.0.0",
        port=TELNET_PORT,
    )
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    print(f"[TELNET] Listening on {addrs}")
    async with server:
        await server.serve_forever()


# ----------------------------------------------------------------------
# HTTP REST API (port 7780) – aiohttp
# ----------------------------------------------------------------------
async def status_handler(request):
    return web.json_response({"status": "ok", "timestamp": time.time()})

async def agents_handler(request):
    world: World = request.app["world"]
    return web.json_response(await world.agent_list())

async def rooms_handler(request):
    world: World = request.app["world"]
    return web.json_response(await world.room_graph())

async def scores_handler(request):
    world: World = request.app["world"]
    return web.json_response(await world.script_scores())

async def generation_handler(request):
    world: World = request.app["world"]
    return web.json_response(await world.generation_stats())

async def inject_scenario_handler(request):
    world: World = request.app["world"]
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    # Very naive validation – you can replace with a proper schema check
    if not isinstance(payload, dict) or "id" not in payload:
        return web.json_response({"error": "scenario must contain an 'id' field"}, status=400)

    async with world._lock:
        world.scenarios.append(payload)

    return web.json_response({"msg": "scenario injected", "scenario": payload})

def create_http_app(world: World) -> web.Application:
    app = web.Application()
    app["world"] = world
    app.router.add_get("/status", status_handler)
    app.router.add_get("/agents", agents_handler)
    app.router.add_get("/rooms", rooms_handler)
    app.router.add_get("/scores", scores_handler)
    app.router.add_get("/generation", generation_handler)
    app.router.add_post("/inject-scenario", inject_scenario_handler)
    return app

async def start_http_server(world: World):
    app = create_http_app(world)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=HTTP_PORT)
    await site.start()
    print(f