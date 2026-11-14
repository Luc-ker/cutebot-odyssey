# T56 — Facing-object detection

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

> **Goal:** Work out which object is directly in front of the robot, so the screen can label it, the video can draw it, and the Shout button can describe it.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | World memory & game logic | §7.2, §7.8 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/facing.py`, `tests/world/test_facing.py`

## Contracts consumed (stub or fake them in your tests)
geometry `in_cone` (T06)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `facing(robot, objects) -> id | None`: objects inside a cone (`FACING_HALF_ANGLE_DEG`, `FACING_MAX_DIST`), pick the nearest, weighted by angle.
- Hysteresis: keep the current target until another is clearly better (20 % score margin) to avoid flicker.
- Clusters count as targets too (use cluster id offset or a tagged result `("cluster", id)`) — document the choice.

## Acceptance criteria
- [ ] Object straight ahead within range → its id; same object behind → None.
- [ ] Two similar targets: no flicker between them across small heading changes.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
