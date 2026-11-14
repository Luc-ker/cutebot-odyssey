# T29 — Restyle prompt composer

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

> **Goal:** Build the text prompt that tells the video model how to redraw the robot's view, combining the world's style with whatever object or giant is right in front of the robot.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Robot's-eye view | §7.2, §7.10 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/prompt_composer.py`, `tests/world/test_prompt_composer.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`world.current`, `world.objects`, `robot.state`, `world.event` giant kinds), C5 (`prompt` phrases)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Base = `world.restyle_prompt`. If `robot.state.facing_id` is set, append that object's role phrase from `roles.json` ("a stone castle tower in the foreground").
- If a giant is present, append a giant phrase suited to the setting ("a towering sea god looming over the horizon").
- Add a fixed tail for consistency ("first-person, low to the ground, consistent lighting").
- Publish `video.prompt` only when the text changes, at most 2 per second; cap at 400 characters.
- Stay silent while a `world.transition` is in progress (from `started` for `duration_ms`); the blender (T30) owns the prompt then.

## Acceptance criteria
- [ ] Facing a `castle` in a kingdom world → prompt contains "stone castle".
- [ ] Identical inputs twice → one publish.
- [ ] Pure function `compose(world, facing_role, giant_present) -> str` tested separately.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
