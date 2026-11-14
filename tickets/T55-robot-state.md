# T55 — Robot state aggregator

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

> **Goal:** Combine where the overhead camera sees the robot with what the robot's own sensors report, into one robot status other parts can rely on.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | World memory & game logic | §9, §7.11 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/robot_state.py`, `tests/world/test_robot_state.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`vision.state`, `robot.telemetry`, `world.objects`, `robot.state`), facing function from T56 (stub in tests)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Track latest pose (`pos`, `heading`, `seen`) and telemetry (`distance_cm`, `override`).
- Compute `facing_id` with `facing(robot, objects)` from T56.
- Publish `robot.state` at 10 Hz; mark telemetry stale (distance null) after 1 s with no packet.

## Acceptance criteria
- [ ] With fake inputs, `robot.state` merges both sources; stale telemetry → `distance_cm: null`.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
