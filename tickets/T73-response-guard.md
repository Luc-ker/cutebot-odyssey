# T73 — Gemini response guard

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

> **Goal:** Check everything Gemini sends back before it can reach the game: wrong shapes are thrown away, unknown roles are replaced, so a bad answer never breaks the demo.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Gemini world composer | §7.7 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/gemini/guard.py`, `tests/gemini/test_guard.py`

## Contracts consumed (stub or fake them in your tests)
C4, C5, C7 (`guard_world`, `validate_world`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Validate against the world schema; if invalid, return `None`.
- Drop roles for object ids that don't exist; replace roles not in the vocabulary (or `giant`) with the closest allowed role by simple string similarity, else the local fallback picker's choice (T51, stub in tests).
- Fill missing objects with fallback roles; truncate over-long text fields; strip URLs and markdown.

## Acceptance criteria
- [ ] Gemini returning `"role":"spaceship"` in an ocean world → replaced by an allowed role.
- [ ] Unknown object id → dropped; missing object → given a role.
- [ ] Non-JSON garbage → `None`.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
