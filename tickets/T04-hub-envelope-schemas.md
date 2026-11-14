# T04 — Hub envelope and topic payload validators

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

> **Goal:** Make every message on the hub checkable, so a malformed message from one part of the system is caught at the edge instead of crashing another part.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Foundation | §6 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `shared/schemas/topics.schema.json`, `server/common/schemas.py` (envelope part), `web/common/schemas.js`, `tests/common/test_envelopes.py`, `web/common/schemas.test.js`

## Contracts consumed (stub or fake them in your tests)
C2, C3

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- One JSON Schema per topic in C3 (in a single file keyed by topic) plus the envelope schema.
- Python `validate_envelope(obj) -> list[str]`, which also validates `data` against the topic schema when one is known.
- JS `validateEnvelope(obj) -> string[]` with the same behaviour (a small hand-written checker is fine; no CDN).
- Unknown topics are allowed but reported as a warning, not an error.

## Acceptance criteria
- [ ] A sample of every topic in C3 passes in both languages; the same malformed samples fail in both.
- [ ] `vision.state` with `pos: [2, 0]` is rejected (outside 0–1).

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
