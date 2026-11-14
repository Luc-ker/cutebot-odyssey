# T53 — Free-space terrain analysis

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

> **Goal:** Work out where the big empty areas of the table are, so they can become open sea, plains or desert on the map, and what the area under the table is.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | World memory & game logic | §7.5, §7.13 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/terrain.py`, `tests/world/test_terrain.py`

## Contracts consumed (stub or fake them in your tests)
C7 (`analyse`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Occupancy grid (e.g. 20×20) from object footprints; find the largest empty rectangles (top 3).
- `open_space` / `under_table` strings come from the world's `terrain`; default from setting keywords when missing.
- Return `open_regions: [{x, y, w, h}]` in table units.

## Acceptance criteria
- [ ] Empty table → one region covering the whole table.
- [ ] One object in the centre → regions avoid it.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
