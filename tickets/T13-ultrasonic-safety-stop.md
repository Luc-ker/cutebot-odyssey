# T13 — Ultrasonic safety stop

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

> **Goal:** The robot uses its ultrasonic sensor to refuse to drive forward into anything closer than a set distance, so it doesn't crash into real objects.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Robot firmware | §7.1, §7.11 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `firmware/cutebot/sonar.py`, `firmware/cutebot/test_sonar_host.py`

## Contracts consumed (stub or fake them in your tests)
Nothing from other tickets.

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `read_cm()` from the Cutebot ultrasonic sensor (trigger/echo pins per vendor docs), median of the last 3 readings, ignore 0/timeouts.
- `gate(throttle, distance_cm) -> throttle`: if distance < `SAFETY_STOP_CM` and throttle > 0, return 0; reversing is always allowed.
- Expose the latest distance for telemetry (T17).

## Acceptance criteria
- [ ] Host test of `gate`: (80, 5) → 0, (−80, 5) → −80, (80, 30) → 80.
- [ ] Manual: drive at a book, robot stops ~`SAFETY_STOP_CM` away and can still reverse.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
