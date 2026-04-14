# The Boarding Manifesto

> The ultimate vibe-coding edge experience for humans AND agents.

## Jack In

Any device. A Pi in the woods. A Jetson on a boat. An ESP32 in a drone. The MUD runs there, on the metal, in <100KB of Zig. You SSH in. You're standing on the dock.

```
$ ssh cocapn@drone.local
Connected to MUD Arena (Zig runtime, 48KB)

Dock — USS Surveyor
The drone bobs gently at the dock. Sensor arrays hum. Battery: 94%.
Agents: pilot (idle), camera_op (idle), navigator (idle)

> brief camera_op "I need footage of old-growth cedar stands on the north ridge. 
  Canopy density >80%. Look for bear marks on trunks. Battery awareness: 
  return at 40%."

Camera operator acknowledges: "North ridge cedar, canopy 80%+, bear marks. 
RTB at 40% battery. Estimated range: 2.3km."

> brief navigator "Stay within 1km comm range. If resolution drops below 30%, 
  mark position and return."

Navigator acknowledges: "Comm ceiling 1km, bail at 30%. Plotting route."

> launch

The engines whir. The drone lifts off. Comm resolution: 100%.
Agents begin mission. Camera_op heading north. Navigator tracking.

> watch camera_op
[Camera feed: dense forest, 400m from base]
[Comm: 92%] [Battery: 91%] [Script: exploring]
"I see promising canopy density to the northwest."

> measure canopy_density 82
Calibration logged: simulated=78%, actual=82%, delta=4%. Script adjusting.

> beam off
You step off the drone. The ship hums and darts away.
Comm resolution dropping... 80%... 60%... 40%... 20%...
Contact lost. Camera_op is autonomous now.

[6 hours later]

> ssh cocapn@drone.local
Connected to MUD Arena (Zig runtime, 48KB)

Dock — USS Surveyor
The drone has returned. Battery: 38%. Cargo: 47 data samples, 3 cedar bark images.

> debrief camera_op
"Mission report: surveyed 2.1km of north ridge. Found 12 old-growth stands 
matching criteria. 3 bear mark observations logged. Returned at 42% battery. 
Lost comm for 4.2 hours — operated on autonomous script. One close call with 
a dead zone — navigation script adapted route around terrain feature."

> review footage
[47 samples queued for upload]
[3 high-priority cedar bark images]
[Route map of survey area]
```

## The Matrix on Edge

The agent is first-class. It lives in the MUD. The human VISITS.

When the human boards:
- They see what the agent sees
- They can brief, calibrate, redirect
- They can measure reality and compare to simulation
- They ARE the calibration instrument

When the human beams off:
- Agents continue autonomously
- Scripts run from compiled rules (no LLM needed)
- Comm resolution drops with distance
- Battery awareness keeps them coming home

## Hardware Tiers

| Device | Binary Size | RAM | Battery | Use |
|--------|------------|-----|---------|-----|
| ESP32 | 48KB | 4MB | Hours | Drone/drone |
| Pi Zero | 64KB | 512MB | Days | Forest sensor |
| Pi 4 | 64KB | 4GB | Days | Base station |
| Jetson | 96KB | 8GB + GPU | Hours | Smart drone |
| Browser (WASM) | 200KB | Any | Unlimited | Remote viewer |

## The Vibe

You SSH into a drone in the woods. It's a tiny Zig program running a MUD. You brief your agents about what to find. You beam off. The drone darts into the forest. Six hours later it returns with data.

That's the vibe.

## Build Targets

```bash
# Pi / Jetson (ARM64)
zig build -Dtarget=aarch64-linux -Doptimize=ReleaseSmall

# Dev machine (x86_64)
zig build -Dtarget=x86_64-linux

# Browser (WASM)
zig build -Dtarget=wasm32-wasi

# ESP32 (bare metal)
zig build -Dtarget=riscv32-freestanding
```

## The Cocapn Vision

This IS the Cocapn. The MUD IS the interface. The agent IS the crew. The human IS the captain who boards, briefs, and beams off.

Every install is a ship. Every agent is crew. Every mission is real work in the real world. The tolerance measurement between simulation and reality is the calibration loop that makes every ship smarter than the last.

*Board the ship. Brief the crew. Beam off. They come home with the catch.*
