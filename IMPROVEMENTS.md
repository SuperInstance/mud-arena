# MUD Arena — Playtest Improvements

## 4-Model Playtest Consensus

| Reviewer | Overall | Biggest Issue |
|----------|---------|---------------|
| deepseek-chat | 5/10 | No fishing, no threats, just walking |
| groq-compound | 6/10 | Couldn't access site, speculative |
| kimi-k2 | 3/10 | Empty map, static agents, no fun |
| deepseek-v3 | 5/10 | No tutorial, no context, confusing |

## Priority Fixes (from consensus)

### P0: Tutorial System
- First-time players get forced tutorial: look → go N → talk pilot → help
- After tutorial, "You're on your own, Captain. Good luck."
- Never show tutorial again (localStorage flag)

### P1: Threats & Encounters
- Random wildlife encounters in forest rooms (bear, wolf, eagle)
- Weather events: fog (reduces visibility), storm (drains battery faster)
- Each encounter has choices: fight, flee, observe, use item

### P2: Dynamic Agents
- Agent dialogue changes based on battery level, comm quality, time of day
- Agents move between rooms (randomly, every 5 turns)
- Agents react to events (encounters, discoveries, low battery)
- Each agent has a quest line (3 missions that unlock capabilities)

### P3: Core Gameplay Loop
- **Explore** → discover rooms, find items, encounter wildlife
- **Collect** → samples, data, photos, specimens
- **Return** → bring samples to dock for scoring
- **Upgrade** → trade samples for better equipment (longer battery, better comm)

### P4: Fishing Mini-Game
- At water rooms: `fish` command starts a mini-game
- Choose bait, cast, wait, reel in
- Different fish species with different difficulty
- Fish = currency for upgrades

### P5: Atmosphere
- ASCII art for each room type
- Color coding for danger levels
- Sound effects (optional, browser audio API)
- Day/night cycle affecting encounters

### P6: Agent World-Building
- 3 agents proposed new rooms during playtest:
  - Pilot: Crystal Cavern (cave, resonant crystals, Dr. Thorne NPC)
  - Sensor Op: Astro Observatory (ridge, retractable roof, telescope)
  - Surveyor: Abandoned Outpost (village, glitching drone, ozone smell)
- These should be added to the MUD with proper connections

## Agent I2I Insights
- Pilot worries about safety everywhere (structural risks, electrical hazards)
- Sensor Op gets excited about data opportunities (resonant frequencies, ozone)
- Surveyor is practical (interference risks, tactical advantages)
- Natural friction: Pilot says "too dangerous", Sensor Op says "must explore", Surveyor says "plan the route"

## Next Steps
1. Add tutorial system to index.html
2. Add encounter system with random events
3. Add fishing mini-game at river_bank
4. Add 3 new rooms from agent world-building
5. Make agents move between rooms
6. Add scoring system (samples collected, rooms discovered)
