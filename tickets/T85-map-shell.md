# T85 — Overhead map page shell and renderer

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

> **Goal:** The second screen: a full-screen canvas that draws the table as a living fantasy map, with layers stacked on top of each other.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Overhead map | §7.13, §4 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/map/index.html`, `web/map/map.js`, `web/map/store.js`, `web/map/store.test.js`

## Contracts consumed (stub or fake them in your tests)
C3 (subscribes `world.*`, `robot.state`, `vision.state`, `audio.*`), C9 (layer interface, `toScreen`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Store keeps the latest message per topic plus `lastBeatT`; layers get it via `update(state)`.
- Render loop at 60 fps: compute table rect (aspect from config), call each layer's `draw(ctx, rect, t, beat)` in order: terrain, transition-under, danger, objects, robot, giants, info, transition-over.
- Load layers with dynamic `import()`; a missing or throwing layer is skipped with a console warning.
- Uses the beat envelope from `web/map/beat.js` (T93) if present, else 0.

## Acceptance criteria
- [ ] Unit test: store merges messages and records beat time.
- [ ] Manual: with only the shell merged, the page shows an empty table outline and no errors break the loop.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
