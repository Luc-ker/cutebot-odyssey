# T19 — Gamepad buttons to actions

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

> **Goal:** Map the gamepad's coloured buttons to Light, Horn, Shout and Reset, and send them to the laptop through the bridge.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Gamepad firmware | §7.1 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `firmware/gamepad/buttons.py`, `firmware/gamepad/test_buttons_host.py`

## Contracts consumed (stub or fake them in your tests)
C6 (`B` packet)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Read the four buttons (pins per joystick:bit docs), debounce 30 ms, fire on press only.
- Send `B,<L|H|S|R>` three times 20 ms apart (radio is lossy); the bridge de-duplicates (T21).
- Long-press Reset (> 1.5 s) is the only way to send `R`, to avoid accidental resets.
- Document the button colours ↔ actions in a comment and in `docs/controls.md`.

## Acceptance criteria
- [ ] Host test: a bouncy press sequence produces exactly one action.
- [ ] Host test: a short Reset press sends nothing; a 2 s press sends `B,R`.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
