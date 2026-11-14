# T44 — Vision state publisher (Jetson main)

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

> **Goal:** The Jetson's main loop: run camera, detectors, tracker, robot and giant finders each frame and publish one clean "what's on the table" message to the laptop 10 times a second.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Overhead vision | §7.3, §9 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `jetson/main.py`, `jetson/state.py`, `jetson/tests/test_state.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`vision.state`), C8 (all Jetson interfaces), Python hub client (T09) — stub each in tests

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Pipeline: camera → detect + generic detect → drop detections overlapping the robot bbox (the phone on it must not become an object) → tracker → re-id → table coords.
- Build `vision.state` (pure function `build_state(tracks, robot_pose, giants, calib, ts)`), publish at `VISION_HZ`.
- Publish `system.health` with fps and number of objects.
- CLI flags: `--hub`, `--camera`, `--file`, `--no-giants`.

## Acceptance criteria
- [ ] Test of `build_state`: a track overlapping the robot is excluded; positions are in [0,1]; schema validates (T04 schema if present).
- [ ] Manual: laptop status page shows `vision.state` arriving at ~10 Hz.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
