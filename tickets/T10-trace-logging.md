# T10 — Structured logging and latency tracing

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

> **Goal:** Consistent logs across every service, with timestamps that let us measure how long things take (joystick to movement, song change to new world) against the responsiveness targets.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | Foundation | §10 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/common/log.py`, `tests/common/test_log.py`

## Contracts consumed (stub or fake them in your tests)
Nothing from other tickets.

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `get_logger(service)` producing one JSON line per event: `ts`, `service`, `level`, `msg`, extra fields.
- `trace(name, **fields)` context manager that logs start, end and `ms`.
- Log level from `GENRATOR_LOG_LEVEL`; logs go to stderr and `logs/<service>.jsonl` (folder git-ignored).
- Never log audio bytes or images (only sizes).

## Acceptance criteria
- [ ] `with trace("gemini.compose"):` writes one line with `ms` ≥ 0.
- [ ] Passing a `bytes` field logs `"<N bytes>"` instead of the content.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
