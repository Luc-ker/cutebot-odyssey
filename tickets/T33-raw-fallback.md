# T33 — Raw-feed fallback mode

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

> **Goal:** If the AI video model drops, the main screen still works: it shows the plain camera feed with a world-coloured tint and labels so the game carries on.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Robot's-eye view | §7.15 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/eye/fallback.js`, `web/eye/fallback.css`, `web/eye/fallback.test.js`

## Contracts consumed (stub or fake them in your tests)
restyler `onStatus` (T28), C3 (`world.current`, `world.objects`, `robot.state`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `mountFallback(container, hub, restyler)`: when status `ok:false` for > 1.5 s, show the raw stream with a palette-coloured gradient overlay and vignette; return to restyled when `ok` again for 3 s.
- Show role labels for the facing object larger than normal.
- Publish `video.status {mode:"raw"}` on switch.

## Acceptance criteria
- [ ] Unit test: status false → fallback visible; true for 3 s → hidden.
- [ ] Manual: unplug network mid-drive, screen switches to tinted raw feed without freezing.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
