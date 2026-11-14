# T75 — Pre-composed fallback worlds

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

> **Goal:** Eight ready-made worlds (ocean, wasteland, snowy village, kingdom, neon city, rainforest, royal court, space station) that can be chosen by button if Gemini is down, and one to start the demo in.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Gemini world composer | §7.6, §7.15 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `shared/worlds/*.json`, `server/world/fallback_worlds.py`, `tests/world/test_fallback_worlds.py`

## Contracts consumed (stub or fake them in your tests)
C4, C7 (`load_fallback_worlds`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- One JSON file per world from the §7.6 table, valid against C4, with empty `roles` (the local picker assigns them), real restyle prompts, narration and palette.
- `music_signature` is a typical value per genre (used only for display).
- Loader validates each file and returns them in a fixed order.

## Acceptance criteria
- [ ] All 8 files validate; names are unique; every palette colour resolves in `shared/colours.json`.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
