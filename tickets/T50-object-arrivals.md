# T50 — New and removed object flow

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

> **Goal:** When someone puts a new object on the table, give it a role in the current world, announce it, and place it on the map; when it's taken away for good, remove it.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | World memory & game logic | §7.5, §7.8, §7.10 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/arrivals.py`, `tests/world/test_arrivals.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`vision.state`, `world.current`, `world.event`), C7 (`ObjectRegistry`, `RoleMemory`, `request_role`, `pick_role`), snapshot HTTP (C8)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- On `Diff.added` for an object with no role in the current world: call `request_role` (Gemini) with a 4 s timeout; on failure use `pick_role` (local).
- Store with `RoleMemory.set`, then publish `world.event object_added {id, role, name, behaviour, announce, from_sky}`.
- `from_sky` is true if a giant was present in any `vision.state` within the previous 3 s.
- On `Diff.removed`: publish `object_removed`.
- At most 2 Gemini object calls in flight; extra arrivals use the local picker immediately.

## Acceptance criteria
- [ ] With a fake Gemini that times out, the local picker's role is used and the event still publishes within 5 s.
- [ ] An object added while a giant is in the last state has `from_sky: true`.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
