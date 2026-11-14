# T15 — Cutebot light effects engine

## What Genrator is (read this first)

**Genrator** (repo `sonar-bot-tune`) is our DurHack 2026 project for the theme *Composition*. A player drives a
palm-sized robot car (an ELECFREAKS Cutebot) around a real table with a handheld gamepad, watching a live feed
from a phone strapped to the robot that an AI video model redraws as a fantasy world. **The music decides the
world:** Gemini listens to a few seconds of whatever is playing, looks at an overhead photo of the table, and
composes a world to match. A sea shanty turns the table into an ocean, heavy metal into a volcanic wasteland, a
lullaby into a snowy night. Every real object on the table gets a role in that world (the chair becomes a castle)
and keeps it, because a Jetson with an overhead camera tracks each object and remembers what it is. A second
screen shows the table as a living fantasy map. The robot's lights and the visuals pulse to the beat, hands
reaching over the table appear as giants, threats make the robot recoil, and a narrator announces what happens.
Change the song and the same table becomes a different world.

Full detail: `genrator-whitepaper.md`. Shared interfaces every ticket codes to: `tickets/CONTRACTS.md`.

---

## This ticket

> **Goal:** Drive the robot's RGB headlights so they can flash to the beat, glow in the world's colours, turn red near threats and warm near friends.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Robot firmware | §7.9, §7.11, §7.12 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `firmware/cutebot/lights.py`, `firmware/cutebot/test_lights_host.py`

## Contracts consumed (stub or fake them in your tests)
C6 (`L` packet)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `apply({"mode", "rgb", "ms"})`: Solid (hold colour), Flash (full colour, then back to the base colour after `ms`), Pulse (fade in and out over `ms`).
- Non-blocking: `tick(now_ms)` is called from the main loop; no `sleep` calls.
- Remember a base colour (last Solid) to return to after Flash/Pulse.
- Write the headlight colours via the Cutebot's I2C protocol (check vendor library).

## Acceptance criteria
- [ ] Host test with a fake writer: Flash red 100 ms over base blue → red at t=0, blue at t=150.
- [ ] Host test: `tick` never blocks longer than 2 ms per call.
- [ ] Manual: lights visibly flash on a test `L,F,255,0,0,100` packet sent from the bridge.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
