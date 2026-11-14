# T28 — Restyler adapter

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

> **Goal:** One small module that sends the robot's camera stream to the chosen video model and returns the redrawn stream, so the rest of the screen never cares which provider we picked.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Robot's-eye view | §7.2, §7.15 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/eye/restyler.js`, `web/eye/restyler.test.js`

## Contracts consumed (stub or fake them in your tests)
C9 (`createRestyler`), C3 (`video.prompt`), provider notes from T27 (if not ready, build against a fake provider that tints frames)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `createRestyler(config)` → `start(stream)`, `setPrompt(text)`, `stop()`, `onStatus(cb)` where status is `{ok, fps, latency_ms}`.
- Provider key read from a page-local prompt or `sessionStorage`, never committed.
- A `fake` provider (canvas filter tinted by prompt keywords) for development and as an always-available offline option.
- Report `ok: false` when no frame has arrived for 1.5 s.

## Acceptance criteria
- [ ] Unit test with the fake provider: `setPrompt` changes the tint; no frames for 1.5 s → `ok:false` status.
- [ ] Manual: switching provider is a one-line config change.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
