# T18 — Gamepad joystick drive sender

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

> **Goal:** Read the ELECFREAKS gamepad's joystick and send driving commands to the robot over radio, many times a second, with no network involved.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Gamepad firmware | §7.1, §10 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `firmware/gamepad/drive.py`, `firmware/gamepad/test_drive_host.py`

## Contracts consumed (stub or fake them in your tests)
C6 (`D` packet)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Read joystick X/Y (pins per the joystick:bit docs), calibrate centre at boot, dead-zone of ~8 %.
- Map to throttle/turn −100..100 with a gentle curve (fine control near centre).
- Send `D` at `DRIVE_HZ` (default 25 Hz) with an incrementing `seq`; keep sending zeros when centred so the failsafe stays fed.
- Pure function `axes_to_drive(raw_x, raw_y, centre) -> (throttle, turn)` for host tests.

## Acceptance criteria
- [ ] Host test: centred stick → (0, 0); full forward → throttle 100; values inside the dead-zone → 0.
- [ ] Manual: robot responds with no noticeable lag (target under 100 ms, §10).

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
