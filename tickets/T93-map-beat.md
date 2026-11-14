# T93 — Beat envelope for the map

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

> **Goal:** One shared "how hard is the beat hitting right now" value so every map layer bobs and pulses in time with the music.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | Overhead map | §7.9 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/map/beat.js`, `web/map/beat.test.js`

## Contracts consumed (stub or fake them in your tests)
C3 (`audio.beat`, `audio.features`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `beatEnvelope(now, lastBeatT, tempoBpm, energy) -> 0..1`: fast attack, decay over ~40 % of the beat period, scaled by energy; 0 when silent.
- Optional anticipation: predict the next beat from tempo to hide network jitter.

## Acceptance criteria
- [ ] Unit tests: 1 at the beat, < 0.2 halfway to the next beat, 0 when silent.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
