# T87 — Map object icon layer

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

> **Goal:** Draw every object on the map as an illustrated icon for its role, with its name, moving when the real object moves.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Overhead map | §7.13, §7.4, §7.5 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/map/layers/objects.js`

## Contracts consumed (stub or fake them in your tests)
C9 (layer), C3 (`world.objects`), icons at `web/map/icons/<icon>.svg` (T88; draw a lettered circle if missing)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Icon size from the object's footprint (min/max clamp), name label below, threats outlined red, friendlies gold.
- Smoothly interpolate positions between updates; bob slightly with `beat`.
- `from_sky` objects drop in with a short landing animation; removed objects fade out.
- Clusters drawn as one place icon with a name, members drawn smaller.

## Acceptance criteria
- [ ] Manual with replay scenes (T47): moving an object moves its icon smoothly; labels stay readable.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
