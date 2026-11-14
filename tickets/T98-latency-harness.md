# T98 — Latency measurement against targets

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

> **Goal:** Measure whether Genrator hits its responsiveness targets (beat to light under 100 ms, object moved to map under half a second, song change to new world in 5–15 s).

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | Integration & ops | §10 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `scripts/latency.py`, `docs/latency.md`

## Contracts consumed (stub or fake them in your tests)
C3 timestamps

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Subscribe to the hub and compute: `audio.beat` → `robot.cmd` lights delay; `vision.state` → `world.objects` delay for moved objects; music change → `world.current` delay (use `--audio-file` with two songs).
- Document a slow-motion phone video method for joystick → movement.
- Write results to `docs/latency.md` against the §10 table.

## Acceptance criteria
- [ ] Script prints percentiles (p50/p95) for each measured path.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
