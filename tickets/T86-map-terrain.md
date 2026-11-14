# T86 — Map terrain layer

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

> **Goal:** Fill the map's empty space with animated terrain in the world's style: rippling water, glowing lava, falling snow, grass, a neon grid.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Overhead map | §7.13, §7.5 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/map/layers/terrain.js`

## Contracts consumed (stub or fake them in your tests)
C9 (layer), C3 (`world.current`, `world.objects.terrain`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Pick a terrain style from setting keywords (ocean/sea → water; volcanic/lava → lava; snow/ice → snow; jungle/forest → grass; city/neon → grid; space → stars; default parchment).
- Procedural animation (no image assets), tinted by the palette; slightly brighter in `open_regions`.
- Beyond the table edge draw "the edge of the world" (cliffs or void).

## Acceptance criteria
- [ ] Manual: each of the 8 fallback worlds shows a distinct, animated background at 60 fps on the demo laptop.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
