# T94 — Map world-transition morph

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

> **Goal:** When the world changes, morph the map from the old world's style to the new one, with every icon transforming into its new role, as a deliberate moment.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | Overhead map | §7.12 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/map/layers/transition.js`

## Contracts consumed (stub or fake them in your tests)
C9 (layer, provides both `transition-under` and `transition-over` draws), C3 (`world.transition`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- At transition start, snapshot the current canvas; draw it over the new world, revealed by an expanding circular wipe from the robot over `duration_ms`.
- Sparkle burst at each object position as the wipe passes.

## Acceptance criteria
- [ ] Manual: selecting a different fallback world shows a smooth 3 s wipe, not a cut.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
