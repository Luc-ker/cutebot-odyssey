# T69 — Local music-change detector

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

> **Goal:** Spot quickly, on the laptop, that the song has changed, so a new world can be composed early instead of waiting for the next timed check.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | Audio pipeline | §7.6, §7.7 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/audio/change.py`, `tests/audio/test_change.py`

## Contracts consumed (stub or fake them in your tests)
C7 audio interfaces (`ChangeDetector`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `ChangeDetector.update(block, ts) -> bool`: compare chroma/energy/tempo statistics of the last 3 s against the previous 8 s; return true once per detected change (cooldown 6 s).
- Silence → music counts as a change.

## Acceptance criteria
- [ ] Concatenated clips of two different generated tracks → one change within 4 s of the switch; a single steady track → none.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
