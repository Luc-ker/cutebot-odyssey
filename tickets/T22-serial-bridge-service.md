# T22 — Laptop serial bridge service

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

> **Goal:** The laptop program that talks to the bridge micro:bit: it turns robot telemetry and button presses into hub messages, and hub robot commands into radio packets.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Bridge | §6, §7.1 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/bridge/serial_bridge.py`, `tests/bridge/test_serial_bridge.py`

## Contracts consumed (stub or fake them in your tests)
C2, C3 (`robot.telemetry`, `gamepad.button`, `robot.cmd`), C6, codec (T05)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Find the micro:bit serial port automatically (USB vendor id 0x0D28), or take it from `GENRATOR_SERIAL_PORT`.
- Read lines → decode → publish `robot.telemetry` or `gamepad.button`.
- Subscribe `robot.cmd` → encode → write a line. Cap outgoing lights to `LIGHT_MAX_HZ`; recoil and rumble are never dropped.
- Reconnect every 2 s if unplugged; publish `system.health`.

## Acceptance criteria
- [ ] Test with a fake serial port: `T,12,0,1,0` → `robot.telemetry {distance_cm: 12, line: [0,1], override: false}`.
- [ ] 50 light commands in one second → at most `LIGHT_MAX_HZ` written; a recoil sent among them is written.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
