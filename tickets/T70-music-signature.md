# T70 — Music signature

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

> **Goal:** A compact fingerprint of a song's feel (tempo, energy, brightness, harmony) used to recognise when an earlier song comes back.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Audio pipeline | §7.12, §9 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/audio/signature.py`, `tests/audio/test_signature.py`

## Contracts consumed (stub or fake them in your tests)
C4 (`music_signature`), C7 (`signature`, `distance`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `signature(samples, rate)` → `{tempo_bpm, energy, brightness, chroma[12]}` (chroma normalised).
- `distance(a, b)` → 0–1 combining tempo difference (octave-aware: 60 and 120 bpm are close), energy, brightness and chroma cosine distance.

## Acceptance criteria
- [ ] Two clips of the same generated track → distance < 0.15; two different tracks → > 0.4.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
