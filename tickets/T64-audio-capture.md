# T64 — Audio input capture

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

> **Goal:** Listen to the music near the laptop (microphone or a cable from a phone) continuously, keeping the last few seconds ready for analysis.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Audio pipeline | §7.6 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/audio/capture.py`, `scripts/list_audio_devices.py`, `tests/audio/test_capture.py`

## Contracts consumed (stub or fake them in your tests)
C7 audio interfaces (`AudioInput`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `AudioInput(config)` using `sounddevice`: device from `AUDIO_DEVICE` (name or index), mono, `AUDIO_RATE`.
- `on_block(cb)` delivers float32 blocks (~23 ms) with timestamps; `last(seconds)` reads from a 30 s ring buffer.
- `--file song.wav` mode that plays a file into the pipeline in real time (for tests and demos without a mic).
- Never write audio to disk.

## Acceptance criteria
- [ ] Test using file mode: `last(5)` returns 5 s of samples matching the file.
- [ ] `list_audio_devices.py` prints devices with indexes.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
