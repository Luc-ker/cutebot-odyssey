# T108 — Acceptance test: giant and threat recoil

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

> **Goal:** Automated end-to-end check of the demo's big moment: a hand on the table becomes a giant, a dropped object becomes a threat, and driving into it makes the robot recoil.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Acceptance tests | §7.10, §7.11, §12 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `tests/acceptance/test_giant_threat.py`

## Contracts consumed (stub or fake them in your tests)
C3, C6, fake serial port for the bridge

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Inject a hand → `giant_enter` and a narration line; drop an object while the hand is present → `object_added from_sky` with a forced threat role from the fake Gemini.
- Drive the fake robot into the danger radius → `robot.cmd recoil`, `sfx.play warning`, red light commands, and an `R,` packet written to the fake serial port.

## Acceptance criteria
- [ ] All expected messages appear in order within the time limits in §10.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
