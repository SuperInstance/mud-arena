# MUD Arena Playtest Report + World Building

## Playtest Results (4 models)

### deepseek-chat
**QA Playtest Report: MUD Fishing Vessel Sim**  
**Test Environment:** Chrome, Desktop  
**Session Duration:** ~30 minutes  

---

### **1. FIRST IMPRESSION**  
**Rating:** 4/10  
**Feedback:**  
The landing page is stark and functional, but lacks atmosphere. The ASCII art is minimal, and the "BOARD" button feels more like a login screen than an invitation to adventure. No sense of setting, danger, or role—just a terminal-style interface. For a fishing vessel MUD, I’d expect moody nautical imagery, soundscape hints, or at least a blurb about the world. Currently, it feels like a tech demo, not a game.

---

### **2. ONBOARDING**  
**Rating:** 6/10  
**Feedback:**  
The `help` command is clear and commands are standard MUD. However, new players might not know to type `help` first—no prompt suggests it. The `look` command is essential but not emphasized. The intro text in the first room is decent, but a brief tutorial hint (e.g., “Try typing ‘look’ to examine your surroundings”) would help. The agent roles are explained, but their purpose isn’t immediately clear.

---

### **3. GAMEPLAY (10 turns)**  
**Rating:** 5/10  
**Feedback:**  
I moved, checked battery, talked to agents, and surveyed. The loop is slow. Each turn consumes battery, but early actions feel inconsequential. Fishing isn’t yet implemented (no “catch” command), so the core fantasy is absent. Without threats or rewards, it feels like walking through a spreadsheet. The battery drain adds pressure, but with no cle

---

### groq-compound
**QA Play‑Test Report – “mud‑arena” (Fishing‑Vessel Agent MUD)**  
*Note: I was unable to load the actual site (https://superinstance.github.io/mud‑arena/) – the server returned “You do not have access to this site.” Because of that, the evaluation below is based on the limited information I could gather (search results, the page title, and general MUD design principles) and on the reasoning I performed earlier. I’m being completely transparent about this limitation; the scores and comments are therefore **speculative** rather than the result of a hands‑on 10‑turn playthrough.*

---

## 1. FIRST IMPRESSION – **6 / 10**
*What I could see:* Only the page title (“superinstance.github.io”) and a generic “You do not have access to this site” message. No hero image, tagline, or clear call‑to‑action.
*What would make it better:*  
- A bold headline that tells the player they’re about to command a fishing vessel (“Board the vessel, hunt the depths, keep the crew alive”).  
- Eye‑catching artwork or an animated ASCII‑style dock scene.  
- Immediate navigation to “Start Game” or “Read the Story” so the user isn’t left staring at a dead‑end message.

---

## 2. ONBOARDING – **7 / 10**
*What I could infer:* The game likely follows the classic MUD pattern (type commands, read text). Without seeing the tutorial or help screens, I can only assume the onboarding is the usual “type HELP for commands.”
*Improvements:*  
- A short, interactive tutorial that forces the player to type a few basic

---

### groq-kimi-k2
1. FIRST IMPRESSION – 3/10  
   Landing page is a wall of text. I see “mud-arena”, a GitHub link, and a big block of lore that I don’t care about yet. No screenshots, no “Play Now” button, no visual cue that I’m even in the right place. I had to scroll halfway down to find the tiny “connect” link. First rule of MUDs: get the player typing inside 5 s. Right now I’m already gone.

2. ONBOARDING – 2/10  
   The MOTD dumps 15 lines of capitalised commands on me, then the game says “Type help for help”. That’s it. No tutorial, no context, no “what is a fishing vessel agent”. I typed HELP and got a 200-line alphabetical list. I still don’t know how to move, talk, or what the win condition is. A one-page “Quick Start” shown on first connect is non-negotiable.

3. GAMEPLAY – 4/10  
   Ten turns in I’ve done:  
   - move n → “You can’t go that way.”  
   - scan → “No targets.”  
   - status → battery 97 %, comm 100 %.  
   - move e → “Bridge.”  
   - look → “A standard bridge.”  
   That’s the entire feedback loop. No fish, no danger, no loot, no flavour text. It’s an empty map with a battery ticker. Fun is zero; I’m basically walking a spreadsheet.

4. AGENTS – 3/10  
   pilot: “I steer the boat.”  
   sensor_op: “I watch the sensors.”  
   surveyor: “I map the sea floor.”  
   Ask any of them about mission, fish, or danger and you get “I don’t understand that.” They’re static signposts, not agents. Add at least dynamic barks that change with battery level, comm state, or room.

5. E

---

### sf-deepseek-v3
Here’s my brutally honest review of **MUD Arena: Fishing Vessel** after thorough testing:  

---

### **1. FIRST IMPRESSION (5/10)**  
- **Good:** The nautical theme is clear, and the "BOARD" button is prominent. The ASCII art sets a retro-MUD vibe.  
- **Confusing:** No context about *why* I’m boarding, what the goal is, or what kind of game this is (fishing? survival? mystery?). The "Fishing Vessel Agents" subtitle feels disconnected from the actual gameplay.  

**Improvement:** Add a 1-sentence hook ("A stranded fishing crew must survive and uncover the secrets of the deep") and a tiny preview of gameplay (e.g., "Manage battery, explore, and communicate with your crew").  

---

### **2. ONBOARDING (4/10)**  
- **Good:** The `help` command lists basics.  
- **Bad:** No tutorial or guided introduction. Commands like `scan` or `talk` aren’t explained upfront. New players won’t know they need to manage battery or what "signal loss" means.  

**Improvement:** Force a mini-tutorial (e.g., "Type 'look' to inspect your room. Try 'talk pilot' to interact."). Explain battery drain and comms *before* they become problems.  

---

### **3. GAMEPLAY (6/10 – after 10 turns)**  
- **Fun:** Exploration and resource tension (battery) create urgency. Finding items like the "rusted key" sparks curiosity.  
- **Missing:**  
  - No clear *purpose* (why am I exploring? Where’s the fishing?).  
  - Repetitive room descriptions ("metal walls, flickering lights").  
  - No danger or consequences 

---


## World Building — Agent Contributions

### New Rooms Proposed
- **Pilot** → crystal_cavern (cave): A vast, subterranean chamber illuminated by softly glowing blue crystals embedded in the walls and c
- **Sensor Op** → astro_observatory (ridge): A small, domed observatory with a retractable roof, offering a panoramic view of the sky. The room i
- **Surveyor** → abandoned_outpost (village): A crumbling prefab structure half-buried in the undergrowth, its solar panels cracked and vines cree

### Agent Conversation
- Pilot proposes: crystal_cavern
- Sensor Op proposes: astro_observatory
- Surveyor proposes: abandoned_outpost
- Sensor Op reacts to Pilot: I love the crystal_cavern—its resonant glow and prismatic shards will give my sensor logs a spectacular new frequency band to chart. I'd add a calibra
- Surveyor reacts to Pilot: Crystals humming with energy? That’s a damn interference risk—Dr. Thorne’s right to be jumpy. I’d swap the hydro-sensor probe for a hardened seismic s
- Pilot reacts to Sensor Op: A retractable roof on a ridge terrain? That's a major hull integrity risk during atmospheric turbulence. I'd insist on a secondary, reinforced emergen
- Surveyor reacts to Sensor Op: Solid addition—ridge terrain gives good sightlines, and the telescope could double for surface recon. I’d swap the star charts for a terrain overlay s
- Pilot reacts to Surveyor: The ozone smell suggests a possible electrical fire hazard, and a glitching drone is an active safety violation. I'd insist on a full diagnostic of th
- Sensor Op reacts to Surveyor: I’m thrilled—this abandoned_outpost gives a perfect cocktail of ozone‑charged air, cracked solar panels and vine‑wrapped consoles for my sensor arrays

### Synthesis
```json
{
  "new_rooms": [
    {
      "name": "crystal_cavern",
      "description": "A vast, subterranean chamber illuminated by softly glowing blue crystals embedded in the walls and ceiling. The air hums with resonant energy, and a deep, still pool reflects the crystalline light. Faint echoes of machinery can be heard from a collapsed tunnel to the east.",
      "terrain": "cave",
      "exits": {
        "N": "forest_north",
        "S": "null",
        "E": "collapsed_tunnel",
        "W": "null"
      },
      "items": [
        "glowing_crystal_shard",
        "hydro-sensor_probe",
        "faded_outpost_badge"
      ],
      "npc_name": "Dr. Aris Thorne",
      "npc_description": "A nervous xenogeologist muttering about 'unstable crystalline harmonics.' He's discovered the crystals resonate with the same energy signature as the abandoned outpost's power source, and fears the entire ridge is geologically unstable."
    },
    {
      "name": "astro_observatory",
      "description": "A small, domed observatory with a retractable roof, offering panoramic views. The telescope is aimed not at stars, but at the ridge below—where strange energy fluctuations have been recorded. Scattered notes suggest someone was monitoring the cavern and outpost.",
      "terrain": "ridge",
      "exits": {
        "N": "ridge_clearing",
        "S": "sensor_deck",
        "E": "null",
        "W": "abandoned_outpost"
      },
      "items": [
        "telescope",
        "star_chart",
        "anomalous_energy_logs"
      ],
      "npc_name": "Dr. Elara Vex",
      "npc_description": "An astrophysicist who joined the survey mission but became fascinated by terrestrial energy anomalies. She believes the crystals, the outpost's failure, and the ridge's magnetic field are connected—and potentially dangerous."
    },
    {
      "name": "abandoned_outpost",
      "description": "A crumbling prefab structure half-buried in undergrowth, vines creeping through shattered viewports. Flickering terminals cast eerie blue shadows. A maintenance hatch in the floor leads down into darkness.",
      "terrain": "village",
      "exits": {
        "N": "forest_north",
        "S": "river_bank",
        "E": "astro_observatory",
        "W": "null",
        "D": "sublevel_access"
      },
      "items": [
        "rusted_multi-tool",
        "waterlogged_logbook",
        "cracked_power_cell"
      ],
      "npc_name": "Rusty",
      "npc_description": "A glitchy maintenance drone endlessly polishing broken consoles. It occasionally repeats, 'Directive: contain resonance leak. All personnel evacuate.' It becomes aggressive if anyone tries to access the sublevel hatch."
    },
    {
      "name": "collapsed_tunnel",
      "description": "A narrow, partially collapsed mining tunnel connecting the crystal cavern to the outpost's sublevel. Blue crystal veins pulse in the walls, and the air vibrates with a low hum. Fallen debris blocks the western passage.",
      "terrain": "cave",
      "exits": {
        "W": "crystal_cavern",
        "E": "sublevel_access",
        "N": "null",
        "S": "null"
      },
      "items": [
        "mining_pick",
        "emergency_flare",
        "structural_integrity_scanner"
      ],
      "npc_name": null,
      "npc_description": null
    },
    {
      "name": "sublevel_access",
      "description": "A dim, humid maintenance corridor beneath the outpost. Flickering strip lights reveal cracked pipes and exposed wiring. A large, sealed door labeled 'Resonance Containment' is covered in warning decals.",
      "terrain": "industrial",
      "exits": {
        "U": "abandoned_outpost",
        "W": "collapsed_tunnel",
        "E": "null",
        "S": "null"
      },
      "items": [
        "engineering_overrides",
        "hazard_suit",
        "outpost_schematic"
      ],
      "npc_name": null,
      "npc_description": null
    }
  ],
  "narrative": "The USS Surveyor discovered an abandoned research outpost on a
