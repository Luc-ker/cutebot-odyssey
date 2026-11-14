# T35 — Giant arrival effect on the robot's-eye view

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

> **Goal:** When someone puts a hand on the table, show a dramatic "giant's hand descends from the sky" moment on the main screen.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | Robot's-eye view | §7.10 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/eye/giant.js`, `web/eye/giant.css`

## Contracts consumed (stub or fake them in your tests)
C3 (`world.event` giant_enter/giant_leave, `world.current`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- On `giant_enter`: darken top of screen, shadow sweeps down, short screen shake, caption ("A frost giant reaches down from the sky") using the world setting.
- On `giant_leave`: shadow lifts.
- Rate limit to one effect every 4 s.

## Acceptance criteria
- [ ] Manual: trigger a fake `giant_enter` from the status page (T97) and see the effect; repeated events within 4 s don't stack.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
