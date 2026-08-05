# Changelog

All notable changes to MUD Arena will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- 26 integration tests covering the full perceive → decide → act cycle:
  - Agent navigation (6 tests): movement, invalid directions, event emission
  - Agent interaction (7 tests): take, drop, examine, talk to NPCs
  - Agent perception (5 tests): exits, items, NPCs, void room
  - Agent inventory (3 tests): empty, after take, use
  - Full simulation (5 tests): treasure hunt, event log, custom decision function

### Fixed
- pytest pythonpath: added `pythonpath = ["src"]` to `[tool.pytest.ini_options]`
  in pyproject.toml. Tests now run with plain `pytest` without PYTHONPATH workaround.

## [0.1.0] - Initial Release

- Room/RoomGraph spatial model with directional exits and navigation
- Agent with pluggable decision functions and full verb set
- Command parser supporting natural language MUD commands
- EventBus for decoupled event-driven communication
- Inventory system with items, tags, consumables, and capacity limits
- CUDA-accelerated simulation kernel (src/mud_arena.cu)
- WebSocket/Telnet/HTTP server for real-time observation
- Scenario generator for LLM-driven world creation
- Evolution engine for breeding agent strategies
- 42 unit tests (now 68 with integration tests)
