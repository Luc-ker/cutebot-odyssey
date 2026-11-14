# T17 — Cutebot telemetry broadcast

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

> **Goal:** The robot reports its ultrasonic distance, edge sensors and whether it is mid-recoil, so the laptop knows when the robot is physically blocked.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Robot firmware | §7.11, §9 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `firmware/cutebot/telemetry.py`, `firmware/cutebot/test_telemetry_host.py`

## Contracts consumed (stub or fake them in your tests)
C6 (`T` packet)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `maybe_send(now_ms, distance_cm, line, override)` sends a `T` packet at 10 Hz max.
- Send immediately (rate permitting) when `override` changes.
- Keep packets ≤ 32 bytes; round distance to an int, cap at 400.

## Acceptance criteria
- [ ] Host test with a fake radio: calls every 10 ms for 1 s produce ~10 packets.
- [ ] An `override` change produces a packet within 100 ms.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
