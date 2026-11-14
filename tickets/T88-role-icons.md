# T88 — Role icon art set

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

> **Goal:** A matching set of map icons, one for every role (castle, ship, dragon, lighthouse...), in a consistent storybook style.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Overhead map | §7.13, §8 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/map/icons/*.svg`, `web/map/icons/README.md`

## Contracts consumed (stub or fake them in your tests)
C5 (`icon` names)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- One SVG per `icon` value in `roles.json` plus `unknown`, `robot`, `giant_hand`.
- 64×64 viewBox, simple shapes, `currentColor` for the main fill so the layer can tint per palette, dark outline for contrast.
- README lists each icon and its source (self-made or a CC0 set with credit).

## Acceptance criteria
- [ ] A script or test checks every `icon` in `roles.json` has a file.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
