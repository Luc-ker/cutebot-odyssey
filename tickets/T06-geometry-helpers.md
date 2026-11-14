# T06 — Table geometry helpers (Python and JS)

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

> **Goal:** Small shared maths for positions on the table: distances, angles, "is this in front of the robot", unit conversion, so every module measures space the same way.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Foundation | §7.3, §7.11 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/common/geometry.py`, `web/common/geometry.js`, `tests/common/test_geometry.py`, `web/common/geometry.test.js`

## Contracts consumed (stub or fake them in your tests)
C1, C7, C9

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Python: `dist`, `angle_to`, `angle_diff` (wrapped to (−π, π]), `in_cone(origin, heading, target, half_angle, max_dist)`, `cm_to_units(cm, axis)` using table size from config.
- JS: `toScreen([x,y], rect)` with letterboxing that keeps the table's aspect ratio, `dist`, `angleTo`.

## Acceptance criteria
- [ ] `angle_diff(π − 0.1, −π + 0.1)` ≈ −0.2.
- [ ] `in_cone([0.5,0.5], 0, [0.6,0.5], 0.3, 0.2)` is true; same target behind the robot is false.
- [ ] `toScreen` keeps a 2:1 table centred in a square rect.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
