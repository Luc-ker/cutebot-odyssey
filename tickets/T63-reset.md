# T63 — Gamepad reset and full demo reset

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

> **Goal:** The gamepad's Reset button recentres the world and replays the arrival narration; a separate one-command reset puts the whole demo back to a clean start between judges.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | World memory & game logic | §7.1, §7.15 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/reset.py`, `scripts/reset_demo.py`, `tests/world/test_reset.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`gamepad.button`, `system.reset`, `narration.say`, `world.current`, `robot.cmd`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Gamepad `reset`: publish `narration.say` with the current world's `narration` (priority 2) and `robot.cmd` lights solid in the base colour.
- `scripts/reset_demo.py`: publishes `system.reset`; every stateful module clears itself on that topic (a rule in CONTRACTS).
- After `system.reset`, this module re-publishes the default fallback world selection (`world.select {name:"kingdom"}`).

## Acceptance criteria
- [ ] Gamepad reset → one narration message with the world's line.
- [ ] Running the script publishes `system.reset` then a `world.select`.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
