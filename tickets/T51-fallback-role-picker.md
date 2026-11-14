# T51 — Local fallback role picker

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

> **Goal:** Give objects sensible roles without Gemini (when it's slow or offline), using the roles list, the world's setting and what kind of object it is.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | World memory & game logic | §7.7, §7.15, §8 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/fallback_roles.py`, `tests/world/test_fallback_roles.py`

## Contracts consumed (stub or fake them in your tests)
C5, C7 (`pick_role`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Score each non-system role: matches world setting keywords (+2), matches detector class (+2), not already taken (+1); deterministic tie-break by hash of object id so results are stable.
- At most one threat per 4 objects unless the world mood is dark.
- Generate a name from simple templates per role ("Old Beacon", "The Salt Queen" style) using a seeded list of adjectives/nouns per setting.

## Acceptance criteria
- [ ] Same inputs → same role and name every time.
- [ ] A `bottle` in an ocean world gets an ocean-suited role (lighthouse, ship...) given the shipped `roles.json`.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
