# T16 — Automatic recoil manoeuvre

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

> **Goal:** When the robot drives into a threat's danger zone, it jolts backwards and turns away by itself for a moment, overriding the player.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Robot firmware | §7.11 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `firmware/cutebot/recoil.py`, `firmware/cutebot/test_recoil_host.py`

## Contracts consumed (stub or fake them in your tests)
Nothing from other tickets.

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `start_recoil(ms)`: first ~60 % of `ms` reverse at a fixed speed, then turn in place; then hand control back.
- `active(now_ms) -> bool` and `command(now_ms) -> (throttle, turn)` used by the main loop instead of joystick input while active.
- A second `start_recoil` while active restarts the timer (no stacking).
- Joystick input is ignored during recoil; the failsafe still applies.

## Acceptance criteria
- [ ] Host test: at t = 10 % of ms the command is reverse; at t = 80 % it is a turn; after ms `active()` is false.
- [ ] Manual: `R,700` from the bridge makes the robot back off and turn even with the stick held forward.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
