# T08 — Hub client for browser pages

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

> **Goal:** A tiny library the browser screens (map, robot's-eye view, phone, sound, status) use to talk to the hub, with automatic reconnect so a blip doesn't kill the demo.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Foundation | §6 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/common/hub.js`, `web/common/hub.test.js`

## Contracts consumed (stub or fake them in your tests)
C2, C9

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `connectHub(url, src)` resolves once open; `pub`, `sub`, `onStatus` as in C2.
- Reconnect with backoff (0.5 s → 5 s) and re-send all subscriptions after reconnect.
- Messages published while disconnected are dropped (not queued), except the last `webrtc.signal`, which is retried once.
- Default URL derived from `location` (`ws`/`wss` to match the page).

## Acceptance criteria
- [ ] Test with a fake WebSocket: subscriptions are re-sent after a simulated reconnect.
- [ ] Callbacks for `vision.*` fire for `vision.state` and not for `world.current`.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
