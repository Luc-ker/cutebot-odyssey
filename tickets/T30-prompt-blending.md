# T30 — Prompt blending during world changes

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

> **Goal:** When the music changes the world, morph the video style gradually from the old world to the new one instead of cutting.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | Robot's-eye view | §7.12 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/prompt_blend.py`, `tests/world/test_prompt_blend.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`world.transition`, `video.prompt`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- On `world.transition`, publish a sequence of `video.prompt` messages over `duration_ms`: old prompt → mixed prompts ("stormy ocean at dusk turning into a volcanic wasteland") → new prompt.
- If the provider supports prompt weights (see T27 doc), use weights; otherwise use 4 textual steps.
- The normal composer (T29) stays quiet during a transition window by itself, so this module owns `video.prompt` for exactly `duration_ms`.

## Acceptance criteria
- [ ] A 3000 ms transition produces 4–6 prompts in order, the last equal to the new world's prompt.
- [ ] A second transition mid-blend starts from the current mixed prompt.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
