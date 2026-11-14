# T89 — Map robot marker and trail

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

> **Goal:** Show the robot as a small explorer marker moving across the map in real time, with a fading trail of where it has been.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Overhead map | §7.13, §7.15 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/map/layers/robot.js`

## Contracts consumed (stub or fake them in your tests)
C9 (layer), C3 (`robot.state`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Marker with a heading arrow; trail of the last ~15 s, fading.
- When `seen` is false, draw the marker frozen and greyed with a "?" (never jump).
- During `override` (recoil), marker flashes red.

## Acceptance criteria
- [ ] Manual with the robot-loop replay scene: smooth marker and trail; unseen robot shows frozen.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
