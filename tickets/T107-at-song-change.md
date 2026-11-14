# T107 — Acceptance test: song change changes the world

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

> **Goal:** Automated end-to-end check that changing the music leads to a new world with new roles, and that playing the first song again brings the first world back.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Acceptance tests | §7.6, §7.7, §7.12 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `tests/acceptance/test_song_change.py`

## Contracts consumed (stub or fake them in your tests)
C3, C7, fake Gemini (local or from T106), audio file mode (T64)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Feed song A → world A adopted; song B → world B with `world.transition`; song A again → `world_changed {returning: true}` and the original roles.
- Gemini timeout case: world holds.

## Acceptance criteria
- [ ] All three phases and the timeout case pass with fakes.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
