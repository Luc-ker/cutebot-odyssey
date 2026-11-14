# T45 — Overhead snapshot endpoint with people blurred

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

> **Goal:** Serve the latest overhead photo of the table to Gemini, with any people blurred out, for composing the world.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Overhead vision | §7.7, §11 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `jetson/snapshot_server.py`, `jetson/tests/test_snapshot_server.py`

## Contracts consumed (stub or fake them in your tests)
C8 (snapshot HTTP), camera `latest()` (T36), giants (T43)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Small HTTP server on `JETSON_HTTP_PORT`: `GET /snapshot.jpg` → JPEG of the latest frame cropped to the table (via calibration), max 1024 px wide, quality ~80.
- Blur all person/hand regions before encoding. Never write images to disk.
- `GET /health` → JSON.

## Acceptance criteria
- [ ] Test with a fake frame and a fake giant box: the returned JPEG region over the box is blurred (low variance).
- [ ] No files are created on disk during the test.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
