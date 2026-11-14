# T62 — World objects publisher

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

> **Goal:** Publish one combined picture of the world 10 times a second: every object with its current role and name, clusters and terrain, for the map and the main screen to draw.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | World memory & game logic | §7.4, §7.13 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/objects_publisher.py`, `tests/world/test_objects_publisher.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`world.objects`), C7 (`ObjectRegistry`, `RoleMemory`, `find_clusters`, `analyse`) — fakes in tests

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Every 100 ms: join registry objects with roles for the current world; objects with no role yet get `role: null`.
- Add `clusters` and `terrain` (recompute clusters/terrain at most 2 Hz).
- Carry `from_sky` from `object_added` events for 3 s so the map can animate a landing.

## Acceptance criteria
- [ ] Output validates against the `world.objects` schema; an object with a remembered role shows it.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
