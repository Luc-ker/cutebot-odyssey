# T72 — World composer prompt

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

> **Goal:** Write the instructions Gemini follows to turn music plus a table photo into a world: setting, mood, a role for every object, a video prompt and a line of narration.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Gemini world composer | §7.7, §8, §3 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/gemini/prompt.py`, `shared/prompts/compose_world.md`, `tests/gemini/test_prompt.py`

## Contracts consumed (stub or fake them in your tests)
C5 (roles vocabulary), C7 (`build_compose_parts`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- System text in `compose_world.md`: listen to the clip, decide the world the music implies, give every listed object a role only from the vocabulary, describe open space and under-table, write a restyle prompt (first-person, low to the ground) and one short in-world narration line (≤ 25 words, no real-world facts).
- Include the current world (if any) and say "keep it unless the music clearly implies a different world".
- Include the object list as `id, class, position` lines and the allowed roles with behaviours.
- `build_compose_parts(...)` returns `[text, audio part, image part]`.

## Acceptance criteria
- [ ] Unit test: every object id and every allowed role appears in the text; prompt under 6 000 characters with 20 objects.
- [ ] A short note in the file explains each rule's reason (for future tuning).

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
