# T66 — Energy and brightness features

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

> **Goal:** Measure how loud, energetic and bright or dark the music sounds, so effects get stronger with energetic music and the world can lean bright or heavy.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Audio pipeline | §7.6, §7.9 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/audio/features.py`, `tests/audio/test_features.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`audio.features`), `AudioInput` (T64), `SilenceGate` (T67)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Every 50 ms: RMS, `energy` = RMS normalised by an adaptive running max (so room level doesn't matter), `brightness` = spectral centroid normalised to 0–1.
- `silent` from the silence gate.
- Publish `audio.features` at 20 Hz.

## Acceptance criteria
- [ ] White noise → brightness higher than a 100 Hz sine; louder signal → higher energy.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
