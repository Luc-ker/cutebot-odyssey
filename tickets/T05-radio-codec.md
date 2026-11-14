# T05 — Radio packet codec (laptop side and micro:bit side)

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

> **Goal:** Turn the short text messages that the micro:bits send over radio into structured data and back, so the gamepad, robot, bridge and laptop speak exactly one protocol.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Foundation | §7.1, §5 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/common/radio_codec.py`, `firmware/common/codec.py`, `tests/common/test_radio_codec.py`

## Contracts consumed (stub or fake them in your tests)
C6

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `encode(dict) -> str` and `decode(str) -> dict | None` for every packet in C6. Bad input returns `None`, never raises.
- Clamp values into range on encode (throttle −100..100, colours 0..255, ms 0..5000).
- `firmware/common/codec.py`: the same functions written for MicroPython (no f-strings dependence issues, no `dataclasses`), small enough to paste into each firmware file.

## Acceptance criteria
- [ ] Round-trip `decode(encode(x)) == x` for one example of every packet type.
- [ ] Every encoded packet is ≤ 32 bytes.
- [ ] `decode("D,abc,1,2")` and `decode("")` return `None`.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
