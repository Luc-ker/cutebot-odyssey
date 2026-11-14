# T31 — Robot's-eye display page

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

> **Goal:** The main screen of the game: the robot's camera feed redrawn as the current world, full-screen.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Robot's-eye view | §7.2, §4 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/eye/index.html`, `web/eye/eye.js`, `web/eye/eye.css`

## Contracts consumed (stub or fake them in your tests)
receiver (T26), restyler (T28), hub (T08), C3 (`video.prompt`, `video.status`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Full-screen video element, black background, keyboard `F` for fullscreen, `R` to force raw mode.
- Wire: phone stream → restyler → video element; `video.prompt` → `restyler.setPrompt`.
- Publish `video.status` every second (`mode`, `latency_ms`).
- Leave slots (absolutely positioned containers) for HUD (T32), pulse (T34), giant effect (T35) and fallback overlay (T33), each loaded as an optional module so a missing file doesn't break the page.

## Acceptance criteria
- [ ] Manual: page shows restyled feed full-screen; with the restyler failing it still shows the raw feed.
- [ ] Missing optional module → console warning only.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
