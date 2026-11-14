# T34 — Beat pulse on the robot's-eye view

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

> **Goal:** Make the main screen pulse subtly in time with the music so the world feels alive even before Gemini has answered.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | Robot's-eye view | §7.9 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/eye/pulse.js`, `web/eye/pulse.css`

## Contracts consumed (stub or fake them in your tests)
C3 (`audio.beat`, `audio.features`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `mountPulse(container, hub)`: on each beat, brief brightness/glow/vignette pulse via CSS variables; strength from `energy`.
- When `silent`, settle to no pulse.
- Respect `prefers-reduced-motion` with a much smaller effect.

## Acceptance criteria
- [ ] Manual: at 120 bpm the screen visibly breathes; quiet music → subtle; silence → still.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
