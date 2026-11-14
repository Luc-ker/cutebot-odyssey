# T24 — Radio contention test bench

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

> **Goal:** Check that light and recoil traffic from the laptop never makes driving laggy, since the gamepad and the bridge share the same radio channel.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | Bridge | §7.15, §10 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `scripts/radio_bench.py`, `firmware/bench/echo.py`, `docs/radio-bench.md`

## Contracts consumed (stub or fake them in your tests)
Nothing from other tickets.

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Echo firmware for a spare micro:bit (standing in for the Cutebot) that answers each `D` packet with a `T` packet whose distance field carries the `seq`, so the bridge forwards it to the laptop.
- A second spare micro:bit sends `D` packets at `DRIVE_HZ` like the gamepad.
- Script sends `L` packets at 0, 5, 10, 20 Hz through the bridge while measuring `D` round-trip loss and latency.
- Write results and the recommended `LIGHT_MAX_HZ` into `docs/radio-bench.md`.

## Acceptance criteria
- [ ] Doc contains a table of loss and latency per light rate and the chosen limit with a reason.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
