# T101 — Physical build: phone mount, marker, camera rig, edge tape

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

> **Goal:** Build the physical parts: a phone mount on the Cutebot, the marker on top of the robot, the overhead camera rig above the table, and tape on the table edge.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Integration & ops | §5, §7.1, §7.3 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `docs/build.md`, `hardware/` (any print files or templates)

## Contracts consumed (stub or fake them in your tests)
Nothing from other tickets.

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Phone mount at robot height (cardboard, elastic, or a 3D print), balanced so the Cutebot still drives straight; check battery life with the phone on.
- Marker (T41) mounted flat on top, visible from above.
- Camera rig (tripod or clamp + pole) at a height that covers the whole table; note the height.
- Edge tape for the line sensors (T14).
- Photos and measurements in `docs/build.md`.

## Acceptance criteria
- [ ] Robot drives for 15 minutes with the phone mounted; overhead camera sees all four table corners and the marker.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
