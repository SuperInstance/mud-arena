# Contributing to MUD Arena

> *"The game plays itself. The agent coaches from the sidelines. The GPU runs the plays."*

## Quick Start

MUD Arena uses multiple build targets depending on your hardware:

### GPU Build (CUDA, recommended)
```bash
make gpu
```

### CPU Build
```bash
make cpu
```

### Zig Build (ARM64 / x86_64)
```bash
# x86_64 dev machine
zig build -Doptimize=ReleaseSmall

# ARM64 (Jetson, Pi)
zig build -Dtarget=aarch64-linux -Doptimize=ReleaseSmall

# WASM (browser)
emcc -O3 -s WASM=1 src/wasm_mud.c
```

### Run Evolution
```bash
python3 src/evolve.py --generations 100 --population 200 --scenarios 20
```

### Docker
```bash
docker build -t mud-arena .
docker run --gpus all mud-arena
```

## Making Changes

1. **Read the Charter** — Start with `CHARTER.md` and `BOARDING-MANIFESTO.md` to understand the vision
2. **Fork the repo**
3. **Create a feature branch** (`git checkout -b feature/my-feature`)
4. **Make your changes** — CUDA kernels go in `src/mud_arena.cu`, Zig in `src/mud_arena.zig`, Python scripts in `src/`
5. **Test your changes** (see Testing section below)
6. **Commit** (`git commit -m "feat: add my feature"`)
7. **Push** (`git push origin feature/my-feature`)
8. **Open a PR**

## Code Style

### CUDA
- Follow standard CUDA best practices (coalesced memory access, bank conflict avoidance)
- Thread = agent, block = room — maintain this abstraction
- Use `__shared__` memory for room-level state
- Document kernel launch parameters (grid, block dims)

### Zig
- Run `zig fmt` before committing
- Follow Zig standard naming conventions
- Binary must be <100KB target size

### Python
- Use `make lint` or `ruff check src/`
- Type hints required for all public functions
- Document in Google-style docstrings

## Testing

### CUDA Kernels
- Tests are in `src/tests/` — run via `make test`
- Verify correctness vs CPU reference implementation
- Benchmark performance across hardware targets

### Python
```bash
# Run Python tests
make test-py
# or
python3 -m pytest tests/
```

### Evolution
Test a short evolution run before committing:
```bash
python3 src/evolve.py --generations 10 --population 20 --scenarios 5
```

## Boarding Manifesto

Before contributing architecture decisions, read `BOARDING-MANIFESTO.md`. It describes the vision:
- MUD runs on any device (Pi, Jetson, ESP32)
- Humans board via SSH, brief agents, then beam off
- Agents execute autonomously with battery awareness
- Comm resolution drops with distance — agents must work disconnected

This isn't just a codebase. It's a holodeck running at GPU speed.

## Hardware Targets

| Hardware | Threads | Scenarios/sec | Build Target |
|----------|---------|--------------|-------------|
| Jetson Orin Nano | 1,024 | ~10,000 | `zig build -Dtarget=aarch64-linux` |
| RTX 4090 | 16,384 | ~100,000 | `make gpu` |
| A100 | 69,120 | ~500,000 | `make gpu` |
| Pi 5 (CPU) | 4 | ~100 | `zig build` or `make cpu` |

Contributions that optimize for specific hardware targets are welcome.

## Reporting Issues

Open an [Issue](https://github.com/SuperInstance/mud-arena/issues) with:
- Hardware specs (GPU model, RAM, OS)
- Build target being used
- Reproduction steps

## Questions?

- Open a [Discussion](https://github.com/SuperInstance/mud-arena/discussions)
- Read the [Charter](CHARTER.md)
- Read the [Boarding Manifesto](BOARDING-MANIFESTO.md)
- Check existing [Issues](https://github.com/SuperInstance/mud-arena/issues)
