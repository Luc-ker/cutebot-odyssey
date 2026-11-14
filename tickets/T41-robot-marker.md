# T41 — Robot marker detection

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

> **Goal:** Find the robot itself from above, using a marker stuck on its top, so the map can show where the explorer is and which way it faces.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Overhead vision | §7.3 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `jetson/robot_marker.py`, `docs/robot-marker.md`, `jetson/tests/test_robot_marker.py`

## Contracts consumed (stub or fake them in your tests)
C8 (`find_robot`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Detect a printed ArUco marker (pick a dictionary and ID, document print size) with OpenCV; return centre, heading (from marker orientation) and bbox.
- Fallback: two coloured dots (front/back) detected by HSV threshold.
- Doc shows how to print and mount the marker so the phone doesn't hide it.

## Acceptance criteria
- [ ] Test with a synthetic image containing the rendered marker rotated 30°: heading within 5°.
- [ ] Returns `None` when absent, without raising.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
