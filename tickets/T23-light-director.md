# T23 — Robot light director

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

> **Goal:** Decide what the robot's lights should do at every moment: flash on the beat in the world's colours, red for danger, warm for friends, dark and still when the music stops.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Bridge | §7.9, §7.11, §7.12 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/bridge/light_director.py`, `tests/bridge/test_light_director.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`audio.beat`, `audio.features`, `world.current`, `world.event`, `world.transition`), `colourFor` equivalent from `shared/colours.json`

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Base colour = first palette colour of the current world; on `world.transition` fade to the new world's colour.
- On `audio.beat`: flash in the second palette colour, flash length and brightness scaled by `energy`.
- On `danger_enter`: red flash train for 1.5 s that overrides beat flashes; on `friendly_enter`: warm pulse.
- When `silent` is true: dim solid base colour, no flashing.
- Publish `robot.cmd {kind:"lights"}`; never more than `LIGHT_MAX_HZ`.

## Acceptance criteria
- [ ] Test with fake hub: 120 bpm beats produce flash commands, rate-limited.
- [ ] During a danger window, beat flashes are suppressed and colour is red.
- [ ] `silent: true` produces one dim solid command and no flashes.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
