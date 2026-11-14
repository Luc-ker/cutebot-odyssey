# T27 — Pick the real-time video restyle model

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

> **Goal:** Decide which real-time video-to-video AI service redraws the robot's camera feed as a fantasy world, by measuring the real options on our network.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Robot's-eye view | §7.2, §10, §14 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `docs/restyle-provider.md`, `scripts/restyle_spike/` (throwaway test pages)

## Contracts consumed (stub or fake them in your tests)
Nothing from other tickets.

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Try 2–3 candidates (for example a hosted real-time video model API, a hosted StreamDiffusion service, StreamDiffusion on a rented GPU).
- For each: end-to-end latency, frame rate, how well a text prompt changes the style, how fast a prompt change takes effect, cost for a weekend, API key setup, browser support (WebRTC or WebSocket frames).
- Recommend one and a backup; write down exactly the API calls needed for `setPrompt` and streaming.

## Acceptance criteria
- [ ] `docs/restyle-provider.md` has a comparison table with measured numbers and a clear recommendation.
- [ ] The spike page for the chosen provider restyles a webcam with a typed prompt.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
