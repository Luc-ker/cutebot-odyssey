# T77 — Talking objects

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

> **Goal:** Stretch goal: drive up to an object and it speaks in character, and remembers you within the session ("Back again, little one?").

| Priority | Component | Whitepaper |
|---|---|---|
| P2: stretch goal | Gemini world composer | §7.14 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/gemini/talk.py`, `tests/gemini/test_talk.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`robot.state`, `world.objects`, `narration.say`), `ask_json` (T71)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- When `facing_id` stays on the same object for 2 s within close range, ask Gemini for one in-character line using the object's role, name, behaviour and how many times the player has visited.
- Cooldown per object 20 s; at most one line in flight.
- Publish `narration.say` with a `voice` hint for that object.

## Acceptance criteria
- [ ] With a fake client, a second visit includes the visit count in the request.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
