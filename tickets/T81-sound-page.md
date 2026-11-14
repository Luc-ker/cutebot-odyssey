# T81 — Sound effects and the sound page

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

> **Goal:** A page on the laptop that plays every sound effect (warning, chime, horns, landings) and speaks narration, driven by hub messages.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Narration & sound | §7.1, §7.8, §7.11 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/sound/index.html`, `web/sound/sound.js`, `web/sound/sfx.js`, `web/sound/sfx.test.js`

## Contracts consumed (stub or fake them in your tests)
C3 (`sfx.play`, `narration.speak`, `narration.done`), C9 (`createSfx`, `createTts` from T80 — stub if absent)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Synthesise sounds with the Web Audio API (no licensed files needed): `warning`, `chime`, `landing`, `whoosh`, `bell`, `horn_<setting>` for the 8 fallback settings, plus every `sfx` name in `roles.json` (fallback to `chime`).
- Big "Start sound" button (browsers need a click to unlock audio); show the last 10 events.
- `narration.speak` → `tts.speak` → publish `narration.done`.
- Duck sound effects by 50 % while narration is speaking.

## Acceptance criteria
- [ ] Unit test: `play("unknown")` plays the fallback without throwing.
- [ ] Manual: each named sound is audible and distinct.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
