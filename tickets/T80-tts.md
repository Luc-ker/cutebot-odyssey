# T80 — Text-to-speech in the browser

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

> **Goal:** Speak the narrator's lines out of the laptop speaker, picking a voice that suits the world where possible.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Narration & sound | §7.8 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/sound/tts.js`, `web/sound/tts.test.js`

## Contracts consumed (stub or fake them in your tests)
C9 (`createTts`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Browser `speechSynthesis`: choose an English voice; map `voice` hints ("deep", "bright", "old", "robotic") to available voices, pitch and rate.
- `speak` resolves on end or error; `cancel()` stops.
- Leave a clearly marked hook for a server TTS (e.g. Gemini TTS) returning audio, not enabled by default.

## Acceptance criteria
- [ ] Unit test with a fake `speechSynthesis`: `speak` resolves after the fake `onend`.
- [ ] Manual: lines are spoken on the demo laptop's speaker.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
