# T42 — Robot pose smoothing and freeze on loss

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

> **Goal:** Turn raw robot sightings into a smooth position and heading in table space, and freeze the robot marker in place (instead of jumping) when the camera loses it.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Overhead vision | §7.3, §7.15 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `jetson/robot_pose.py`, `jetson/tests/test_robot_pose.py`

## Contracts consumed (stub or fake them in your tests)
C1, C8 (`RobotPose`), calibration interface (T37)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Convert pixel position to table coords, heading via two transformed points.
- Exponential smoothing on position; circular smoothing on heading.
- Reject jumps larger than physically possible in one frame.
- `None` measurement → keep last pose, `seen: false`; after 3 s unseen keep frozen.

## Acceptance criteria
- [ ] Test: a single outlier measurement is ignored; a sequence of `None` keeps the last pose with `seen: false`.
- [ ] Heading smoothing works across the ±π wrap.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
