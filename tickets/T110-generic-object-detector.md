# T110 — Generic detector for non-catalogue objects

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

> **Goal:** Detect things the AI model has no name for (crisp packets, cables, toys) as generic "objects", because the demo drops a crisp packet onto the table to create a threat.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | Overhead vision | §7.3, §7.5, §12 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `jetson/generic_detector.py`, `jetson/tests/test_generic_detector.py`

## Contracts consumed (stub or fake them in your tests)
C8 (`GenericDetector`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Learn an empty-table background (median of frames at start and on reset); foreground blobs above a minimum area become `Detection` with `cls: "object"`.
- Drop blobs overlapping known detections (IoU > 0.3), the robot, or touching the table edge (those are giants).
- Optional: an open-vocabulary detector instead, if fps allows (note in a comment).

## Acceptance criteria
- [ ] Test with synthetic frames: a new rectangle on an empty background → one detection; the same rectangle already covered by a known detection → none.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
