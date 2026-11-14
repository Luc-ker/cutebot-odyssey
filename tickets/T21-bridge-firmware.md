# T21 — Bridge micro:bit firmware (serial ↔ radio)

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

> **Goal:** A micro:bit plugged into the laptop that relays messages between the laptop (over USB) and the robot and gamepad (over radio).

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Bridge | §5, §6 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `firmware/bridge/main.py`, `firmware/bridge/test_bridge_host.py`

## Contracts consumed (stub or fake them in your tests)
C6

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Serial at 115200: each newline-terminated line from the laptop is sent over radio unchanged (if it passes the codec).
- Every radio packet received of type `T` or `B` is written to serial as one line.
- De-duplicate repeated `B` packets within 150 ms.
- Ignore `D` packets (they are gamepad→robot traffic) so the serial line stays quiet.

## Acceptance criteria
- [ ] Host test with fake serial/radio: `L,F,255,0,0,100\n` in → same packet out on radio.
- [ ] Three identical `B,H` packets 20 ms apart → one serial line.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
