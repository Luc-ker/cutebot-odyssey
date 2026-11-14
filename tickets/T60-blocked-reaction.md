# T60 — Physical-block detection

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

> **Goal:** When the robot is physically blocked by a real object, describe it as a wall, cliff or reef in the world.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | World memory & game logic | §7.11 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/blocked.py`, `tests/world/test_blocked.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`robot.state`, `world.current`, `world.event`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Blocked = `distance_cm` < `SAFETY_STOP_CM + 2` for > 1 s while the robot's position hasn't changed by > 1 cm.
- Obstacle word: facing object's name if any, else a setting-based word (sea → "reef", wasteland → "lava wall", snow → "ice cliff", default "wall") from a small table in the file.
- Publish `world.event blocked {obstacle}`; cooldown 6 s.

## Acceptance criteria
- [ ] Sustained close distance + no movement → one `blocked` event with the expected word.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
