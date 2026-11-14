# T32 — Robot's-eye HUD overlay

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

> **Goal:** Small on-screen overlay showing the world's name, the role of the object the robot is facing, and a beat indicator.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Robot's-eye view | §7.2 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/eye/hud.js`, `web/eye/hud.css`, `web/eye/hud.test.js`

## Contracts consumed (stub or fake them in your tests)
C3 (`world.current`, `world.objects`, `robot.state`, `audio.beat`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Top-left: world name in a style tinted by the palette. Bottom-centre: "Ahead: The Salt Queen (ship)" when `facing_id` is set, fading out after 2 s without a target.
- Corner beat dot that pops on each `audio.beat`.
- Export `mountHud(container, hub)`.

## Acceptance criteria
- [ ] Unit test with fake hub (jsdom or DOM stub): facing id → label shows name and role.
- [ ] Text readable on both light and dark video (text shadow/backing).

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
