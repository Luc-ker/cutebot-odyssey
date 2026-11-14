# T90 — Map danger glow layer

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

> **Goal:** Show a glowing danger zone around every threat on the map, so players can see where not to drive.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | Overhead map | §7.11, §7.13 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/map/layers/danger.js`

## Contracts consumed (stub or fake them in your tests)
C9 (layer), C3 (`world.objects`, `world.event` danger_enter)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Radial red/orange glow at `DANGER_RADIUS` around threats, breathing with the beat.
- Brighten the zone the robot is currently inside.

## Acceptance criteria
- [ ] Manual: glow sizes match the radius used by T57 (both read config).

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
