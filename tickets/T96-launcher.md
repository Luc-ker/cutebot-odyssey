# T96 — One-command launcher

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

> **Goal:** Start the whole laptop side of Genrator (hub, game brain, serial bridge, replay or live vision) with one command, and stop it all cleanly.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Integration & ops | §7.15 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `scripts/launch.py`, `docs/running.md`

## Contracts consumed (stub or fake them in your tests)
C10, health topic

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `python scripts/launch.py [--replay scene] [--audio-file song.wav] [--no-bridge]`: start hub, brain (T104), serial bridge (T22) as subprocesses with prefixed logs; optionally SSH-start the Jetson service.
- Wait until each service reports `system.health ok` (timeout 20 s) and print the page URLs (eye, map, sound, status, phone).
- Ctrl-C stops everything.

## Acceptance criteria
- [ ] With `--replay`, a fresh clone starts and shows healthy services in under 20 s (manual check documented in `docs/running.md`).

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
