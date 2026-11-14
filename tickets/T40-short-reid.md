# T40 — Short-term re-identification

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

> **Goal:** When an object is briefly hidden by a hand or the robot, or lifted and put back, it gets its old ID back, so it keeps its role in the world.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Overhead vision | §7.4 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `jetson/reid.py`, `jetson/tests/test_reid.py`

## Contracts consumed (stub or fake them in your tests)
C8 (`ReId`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Remember lost tracks for `OBJECT_GRACE_S` with class, last position, size and a small colour histogram.
- A new track that matches a remembered one (same class or compatible, near, similar histogram) is relabelled with the old ID.
- Maintain the mapping so later frames of the new track keep the old ID.

## Acceptance criteria
- [ ] Test: track 7 disappears for 2 s, a new track with the same class appears 3 cm away → output ID 7.
- [ ] After the grace period, a new object gets a new ID.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
