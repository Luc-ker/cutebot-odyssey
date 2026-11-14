# T09 — Hub client for Python services

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

> **Goal:** The Python equivalent of the browser hub client, used by the Jetson vision service and the laptop game logic to publish and subscribe.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Foundation | §6 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/common/hub_client.py`, `tests/common/test_hub_client.py`

## Contracts consumed (stub or fake them in your tests)
C2

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `HubClient.connect(url, src)`, `pub(topic, data)` (fills `ts`, `src`), `sub(pattern, async_cb)`.
- Reconnect with backoff, re-subscribe after reconnect.
- One callback raising must not stop delivery to other callbacks (log and continue).
- Plain `websockets` dependency only, so it also runs on the Jetson.

## Acceptance criteria
- [ ] Test against a minimal in-test WebSocket server: pub/sub round-trip, resubscribe after the server restarts.
- [ ] A callback that raises is logged and the next message is still delivered.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
