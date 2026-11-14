# T07 — Hub server (WebSocket pub/sub plus static files)

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

> **Goal:** The message switchboard on the laptop that every part of Genrator (Jetson, browser screens, phone, game logic) connects to, and the web server for the pages.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Foundation | §6 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/hub/server.py`, `server/hub/__main__.py`, `tests/hub/test_server.py`

## Contracts consumed (stub or fake them in your tests)
C2, C10 (HUB_PORT, TLS_CERT, TLS_KEY)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- asyncio WebSocket server at `/hub` implementing C2: `sub` with prefix `*` patterns, `pub` fan-out to matching subscribers, never echo to the sender unless it subscribed.
- Serve `web/` at `/` and `shared/` at `/shared/` over the same port.
- If `TLS_CERT` and `TLS_KEY` are set, serve HTTPS/WSS (phones need HTTPS for the camera).
- A slow client must not block others: per-client bounded queue (drop oldest for `vision.*`, `audio.*`, `robot.state`, `world.objects`; never drop `world.event`, `narration.*`).
- Publish its own `system.health` every 2 s.
- Run with `python -m server.hub`.

## Acceptance criteria
- [ ] Test: client A subscribes `vision.*`, client B publishes `vision.state` → A receives it unchanged; a `world.current` message is not delivered to A.
- [ ] A client that never reads does not delay delivery to a second client (test with a stalled socket).
- [ ] `GET /shared/config.json` returns the file.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
