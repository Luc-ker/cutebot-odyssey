# T109 — Acceptance test: graceful degradation

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

> **Goal:** Automated check that the demo keeps going when parts fail: Gemini down, video model down, robot lost by the camera, Jetson silent.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Acceptance tests | §7.15 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `tests/acceptance/test_degradation.py`

## Contracts consumed (stub or fake them in your tests)
C3, C7

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Gemini fake always failing → current world holds and `world.select` still works.
- Vision stops sending the robot → `robot.state` keeps the last pose with `seen: false`.
- `vision.state` stops entirely → objects remain for the grace period, then are removed; no crash.
- Bridge serial port unplugged → driving is unaffected (radio only), the bridge reports `system.health ok:false` and recovers when plugged back in (fake port).
- (The video model failing is covered at unit level by T33.)

## Acceptance criteria
- [ ] Each scenario passes with no unhandled exceptions in logs.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
