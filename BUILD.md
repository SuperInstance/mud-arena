## Build Targets

| Target | Command | Binary | Runs On |
|--------|---------|--------|---------|
| ARM64 | `zig build -Dtarget=aarch64-linux -Doptimize=ReleaseSmall` | ~64KB | Pi, Jetson, Thor |
| x86_64 | `zig build -Doptimize=ReleaseSmall` | ~64KB | Dev machine |
| WASM | `emcc -O3 -s WASM=1 src/wasm_mud.c` | ~200KB | Any browser |
| ESP32 | `zig build -Dtarget=riscv32-freestanding` | ~48KB | Drone/drone |

## The Vision

Every Cocapn install runs this MUD. The human boards via SSH, briefs agents on what to find, calibrates tolerances, then beams off. Agents execute autonomously. Comm resolution drops with distance. Battery awareness keeps them coming home.

See [BOARDING-MANIFESTO.md](BOARDING-MANIFESTO.md) for the full experience.