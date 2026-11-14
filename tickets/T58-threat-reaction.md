# T58 — Threat reaction (recoil, warning, rumble)

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

> **Goal:** When the robot enters a dragon's or serpent's zone, make it physically recoil, play a warning sound and buzz the controller.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | World memory & game logic | §7.11, §12 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/threat_reaction.py`, `tests/world/test_threat_reaction.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`world.event` danger_enter, `robot.cmd`, `sfx.play`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- On `danger_enter`: publish `robot.cmd {kind:"recoil", ms: RECOIL_MS}`, `sfx.play {sound:"warning"}`, `robot.cmd {kind:"rumble", ms: 300}`.
- Global cooldown 2.5 s so the robot can escape.
- Lights and narration are handled elsewhere (T23, T82); don't publish them here.

## Acceptance criteria
- [ ] One `danger_enter` → exactly one recoil, one warning and one rumble.
- [ ] A second `danger_enter` 1 s later → nothing.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
