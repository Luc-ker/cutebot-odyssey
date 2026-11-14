# T95 — World transition coordinator

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

> **Goal:** Turn "the world changed" into one timed transition event that the map, video, lights and narrator all follow, so the change feels like one deliberate moment.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | World transitions | §7.12 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/transitions.py`, `tests/world/test_transitions.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`world.current`, `world.transition`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- On `world.current` with a new world id: publish `world.transition {from, to, started, duration_ms: TRANSITION_MS}`.
- Ignore repeats of the same id (the 5 s re-publish); if a new change arrives mid-transition, start a new one from the current target.

## Acceptance criteria
- [ ] Two `world.current` messages with the same id → one transition.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
