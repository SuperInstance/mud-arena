```python
"""
human_mud_interface.py

A lightweight asynchronous client for a text‑based MUD (Multi‑User Dungeon) that
supports three distinct output modes:

1. NORMAL – classic adventure description strings.
2. CALIBRATION – numeric telemetry with simulated values, error estimates,
   and status flags.
3. AGENT_VIEW – the raw perspective of a specific in‑game agent (useful for
   debugging scripted agents).

The client automatically falls back to a simple stdin/stdout “offline” mode
when a WebSocket connection cannot be established.

Typical usage:

    from human_mud_interface import TerminalInterface, Mode

    async def main():
        iface = TerminalInterface('localhost', 8765)
        await iface.connect()
        iface.set_mode(Mode.NORMAL)

        # Normal gameplay
        print(await iface.send_command('look'))

        # Switch to calibration mode and record a measurement
        iface.set_mode(Mode.CALIBRATION)
        print(iface.measure('engine_temp', 180.2, '°C'))

        # Debug a particular agent
        iface.watch_agent('agent_42')
        print(await iface.send_command('status'))

        await iface.disconnect()

    asyncio.run(main())
"""

import asyncio
import json
import sys
from enum import Enum, auto
from typing import Optional

# Optional import – the library is only required for online mode.
try:
    import websockets
except Exception:  # pragma: no cover
    websockets = None  # type: ignore


class Mode(Enum):
    """Supported output modes."""
    NORMAL = auto()
    CALIBRATION = auto()
    AGENT_VIEW = auto()


class TerminalInterface:
    """
    Core client class.

    Parameters
    ----------
    host : str
        Hostname or IP address of the MUD server.
    port : int
        TCP port of the MUD server.
    """

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._mode: Mode = Mode.NORMAL
        self._agent_id: Optional[str] = None
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._offline: bool = False

        # Internal storage for the most recent calibration data.
        self._calibration_store = {}

    # --------------------------------------------------------------------- #
    # Connection handling
    # --------------------------------------------------------------------- #
    async def connect(self) -> None:
        """
        Establish a WebSocket connection to the MUD server.
        If the connection fails (or websockets is unavailable) the client
        switches to offline mode, where commands are echoed back.
        """
        if websockets is None:
            self._offline = True
            print("[INFO] websockets library not available – using offline mode.")
            return

        uri = f"ws://{self.host}:{self.port}"
        try:
            self._ws = await websockets.connect(uri)
            print(f"[INFO] Connected to MUD server at {uri}")
        except (OSError, websockets.InvalidURI, websockets.InvalidHandshake):
            self._offline = True
            self._ws = None
            print(f"[WARN] Could not connect to {uri} – falling back to offline mode.")

    async def disconnect(self) -> None:
        """Close the WebSocket connection if one exists."""
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        self._offline = True
        print("[INFO] Disconnected from MUD server.")

    # --------------------------------------------------------------------- #
    # Mode management
    # --------------------------------------------------------------------- #
    def set_mode(self, mode: Mode) -> None:
        """Switch the client output mode."""
        if not isinstance(mode, Mode):
            raise ValueError("mode must be an instance of Mode Enum")
        self._mode = mode
        print(f"[INFO] Mode set to {self._mode.name}")

    # --------------------------------------------------------------------- #
    # Core command handling
    # --------------------------------------------------------------------- #
    async def send_command(self, cmd: str) -> str:
        """
        Send a raw command string to the server and return the response.

        In offline mode the command is simply echoed back with a prefix.
        """
        if self._offline or self._ws is None:
            # Very simple offline emulation – useful for UI testing.
            return f"[OFFLINE] Echo: {cmd}"

        # Wrap the command with mode information so the server can tailor its
        # response (if the server implements such a protocol).  The payload is
        # JSON to keep it extensible.
        payload = {
            "command": cmd,
            "mode": self._mode.name,
            "agent_id": self._agent_id,
        }
        await self._ws.send(json.dumps(payload))
        raw = await self._ws.recv()
        # Assume the server returns a JSON object with a "response" field.
        try:
            data = json.loads(raw)
            return data.get("response", raw)
        except json.JSONDecodeError:
            # Fallback – server sent plain text.
            return raw

    # --------------------------------------------------------------------- #
    # Calibration utilities
    # --------------------------------------------------------------------- #
    def measure(self, variable: str, actual_value: float, unit: str) -> str:
        """
        Record a calibration measurement for *variable*.

        The method updates an internal store with the latest simulated value,
        computes a simple error metric against the previously stored value,
        and returns a formatted string suitable for CALIBRATION mode.

        The function is a no‑op when the client is not in CALIBRATION mode.
        """
        if self._mode != Mode.CALIBRATION:
            return "[ERROR] Calibration measurement ignored – not in CALIBRATION mode."

        # Retrieve the previous measurement (if any) to compute drift.
        prev = self._calibration_store.get(variable)
        simulated = actual_value  # In a real system this could be a model output.
        error_pct = 0.0
        status = "OK"

        if prev is not None:
            # Simple percentage error relative to the previous measurement.
            diff = simulated - prev["simulated"]
            error_pct = (abs(diff) / prev["simulated"]) * 100 if prev["simulated"] != 0 else 0.0
            status = "DRIFTING" if error_pct > 1.0 else "OK"

        # Store the new measurement.
        self._calibration_store[variable] = {
            "simulated": simulated,
            "last_measured": prev["simulated"] if prev else simulated,
            "unit": unit,
        }

        # Build the human‑readable calibration line.
        return (
            f"{variable}: simulated={simulated:.2f}{unit}, "
            f"last_measured={self._calibration_store[variable]['last_measured']:.2f}{unit}, "
            f"error={error_pct:.1f}%, status:{status}"
        )

    # --------------------------------------------------------------------- #
    # Agent view handling
    # --------------------------------------------------------------------- #
    def watch_agent(self, agent_id: str) -> None:
        """
        Switch the client to AGENT_VIEW mode for *agent_id*.

        Subsequent commands will be sent with the agent identifier attached,
        allowing the server to return the perspective of that specific agent.
        """
        self._agent_id = agent_id
        self.set_mode(Mode.AGENT_VIEW)
        print(f"[INFO] Now watching agent '{agent_id}'")

    # --------------------------------------------------------------------- #
    # Simulation control
    # --------------------------------------------------------------------- #
    async def pause(self) -> None:
        """Tell the server to pause the simulation (if supported)."""
        if self._offline:
            print("[INFO] Pause ignored – offline mode.")
            return
        await self._ws.send(json.dumps({"control": "pause"}))
        print("[INFO] Pause command sent.")

    async def resume(self) -> None:
        """Tell the server to resume the simulation (if supported)."""
        if self._offline:
            print("[INFO] Resume ignored – offline mode.")
            return
        await self._ws.send(json.dumps({"control": "resume"}))
        print("[INFO] Resume command sent.")


# ------------------------------------------------------------------------- #
# Simple interactive demo (executed when the module is run directly)
# ------------------------------------------------------------------------- #
if __name__ == "__main__":
    async def _demo():
        iface = TerminalInterface("localhost", 8765)
        await iface.connect()

        # Basic REPL loop – useful for quick manual testing.
        while True:
            try:
                cmd = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[INFO] Exiting.")
                break

            if not cmd:
                continue

            if cmd.lower() in {"quit", "exit"}:
                break
            elif cmd.startswith("mode "):
                _, mode_name = cmd.split(maxsplit=1)
                try:
                    iface.set_mode(Mode[mode_name.upper()])
                except KeyError:
                    print("[ERROR] Unknown mode. Available: NORMAL, CALIBRATION, AGENT_VIEW")
            elif cmd.startswith("measure "):
                # Expected format: measure <var> <value> <unit>
                parts = cmd.split()
                if len(parts) != 4:
                    print("[ERROR] Usage: measure <variable> <value> <unit>")
                    continue
                _, var, val_str, unit = parts
                try:
                    val = float(val_str)
                except ValueError:
                    print("[ERROR] Value must be numeric.")
                    continue
                print(iface.measure(var, val, unit))
            elif cmd.startswith("watch "):
                _, agent_id = cmd.split(maxsplit=1)
                iface.watch_agent(agent_id)
            elif cmd == "pause":
                await iface.pause()
            elif cmd == "resume":
                await iface.resume()
            else:
                # Forward any other command to the server.
                response = await iface.send_command(cmd)
                print(response)

        await iface.disconnect()

    # Run the demo REPL.
    asyncio.run(_demo())
```