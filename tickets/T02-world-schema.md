# T02 — World JSON Schema, validator and colour words

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

> **Goal:** A machine-checkable definition of what a "world" looks like, so the Gemini guard, the fallback worlds and the screens all agree on the same shape.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Foundation | §7.7, §9 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `shared/schemas/world.schema.json`, `shared/colours.json`, `server/common/schemas.py` (world part), `web/common/colours.js`, `tests/common/test_world_schema.py`

## Contracts consumed (stub or fake them in your tests)
C4

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Write `world.schema.json` (JSON Schema draft 2020-12) for C4: required fields, `behaviour` enum, `palette` exactly 3 strings, `chroma` 12 numbers, string length caps (name ≤ 40, narration ≤ 300, restyle_prompt ≤ 400).
- `validate_world(obj) -> list[str]` returns human-readable errors (empty list means valid).
- `shared/colours.json`: ~80 colour words and phrases Gemini is likely to use ("deep teal", "storm grey", "lantern gold", "lava red", "neon pink"...) mapped to RGB.
- `colourFor(word)` in JS: exact match, then last-word match ("storm grey" → "grey"), else a neutral default.

## Acceptance criteria
- [ ] The whitepaper §7.7 example (plus `id` and `music_signature`) validates with no errors.
- [ ] Missing `restyle_prompt` and `behaviour: "evil"` each produce a clear error.
- [ ] `colourFor("storm grey")` and `colourFor("grey")` return the same RGB when only "grey" is listed.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
