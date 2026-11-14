# T57 — Danger and friendly proximity events

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

> **Goal:** Notice when the robot drives into a threat's danger zone or close to a friendly place, and announce it so lights, sounds and the robot itself can react.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | World memory & game logic | §7.11 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/proximity.py`, `tests/world/test_proximity.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`robot.state`, `world.objects`, `world.event`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Threats have radius `DANGER_RADIUS`, friendlies `FRIENDLY_RADIUS` (plus half their size).
- Publish `danger_enter`/`danger_exit` and `friendly_enter` with hysteresis (exit at 1.2× radius).
- Ignore when `robot.state.seen` is false.
- Per-object cooldown of 3 s for enter events.

## Acceptance criteria
- [ ] A robot path through a threat zone produces exactly one enter and one exit.
- [ ] Unseen robot → no events.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
