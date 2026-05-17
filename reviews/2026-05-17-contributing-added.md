# CONTRIBUTING.md Added — MUD Arena

**Date:** 2026-05-17
**Action:** Created `CONTRIBUTING.md`

## Why This Repo Needed It

MUD Arena is the gold-standard README in the SuperInstance org, but it had zero contribution guidance. Despite having an excellent README, BUILD.md, BOARDING-MANIFESTO.md, and CHARTER.md, there was no single place telling a new developer:

- How to set up a dev environment
- What build targets are available (Zig, CUDA, CPU, WASM, Docker)
- What coding standards to follow
- How to write tests
- How to propose changes

New contributors had to piece together guidance from multiple files. The CONTRIBUTING.md now serves as the single entry point for development workflow.

## What the Contribution Workflow Looks Like

1. Read `CHARTER.md` and `BOARDING-MANIFESTO.md` first (vision context)
2. Fork and create a feature branch
3. Build for target platform (`make gpu`, `zig build`, etc.)
4. Write tests for CUDA kernels, Python scripts, or Zig code
5. Run `make test` / `make test-py` / `zig test`
6. Open PR with clear description of changes and hardware tested

## Special Notes

- **Boarding Manifesto**: This repo isn't just code — it's a holodeck vision. Contributors should read `BOARDING-MANIFESTO.md` before making architecture decisions. The MUD is designed to run on edge devices (Pi, Jetson, ESP32) with battery awareness and disconnected operation.
- **Multiple Build Targets**: Unlike typical repos, MUD Arena has four build paths (CUDA GPU, CPU fallback, Zig native, WASM). The CONTRIBUTING.md documents all of them.
- **Multi-Language**: Code lives in CUDA (`src/mud_arena.cu`), Zig (`src/mud_arena.zig`), C (`src/wasm_mud.c`), and Python (`src/evolve.py`). Each has its own conventions.
