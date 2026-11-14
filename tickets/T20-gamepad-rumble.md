# T20 — Gamepad rumble on threat

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

> **Goal:** Make the controller vibrate when the robot hits a threat, so the player feels the danger.

| Priority | Component | Whitepaper |
|---|---|---|
| P2: stretch goal | Gamepad firmware | §7.11 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `firmware/gamepad/rumble.py`, `firmware/gamepad/test_rumble_host.py`

## Contracts consumed (stub or fake them in your tests)
C6 (`V` packet)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- On `V,<ms>`, run the joystick:bit vibration motor for `ms` (cap 1000), non-blocking.
- Ignore new rumble while one is running unless it is longer.

## Acceptance criteria
- [ ] Host test: `V,300` turns the fake motor on, then off after 300 ms.
- [ ] Manual: sending `V,300` from the bridge buzzes the gamepad.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
