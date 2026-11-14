# T79 — Narration queue

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

> **Goal:** Make sure the narrator speaks one line at a time, important lines first, short, and never talking over itself.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Narration & sound | §7.8 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/narration/queue.py`, `tests/narration/test_queue.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`narration.say`, `narration.speak`, `narration.done`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Priority queue (3 highest); drop items older than 8 s; max queue length 4 (drop the lowest priority).
- Truncate at a sentence boundary to `NARRATION_MAX_CHARS`.
- Publish one `narration.speak` at a time; wait for `narration.done` with matching id or a timeout of `len(text)/12 + 2` seconds.
- De-duplicate identical text within 10 s.

## Acceptance criteria
- [ ] Two `say`s in quick succession → second speak only after the first `done`.
- [ ] A priority 3 message jumps ahead of queued priority 1 messages.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
