# T01 — Shared config file with Python and JS loaders

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

> **Goal:** One place for every tunable number (ports, distances, timings, thresholds) that the laptop, the browser pages and the Jetson all read, so nobody hard-codes values.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Foundation | §6, §10 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `shared/config.json`, `server/common/config.py`, `web/common/config.js`, `tests/common/test_config.py`, `web/common/config.test.js`

## Contracts consumed (stub or fake them in your tests)
C10 (key list)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Create `shared/config.json` with every key in C10 and a sensible default (e.g. `HUB_PORT` 8765, `SAFETY_STOP_CM` 8, `OBJECT_GRACE_S` 5, `GEMINI_INTERVAL_S` 8, `CLIP_SECONDS` 7, `TRANSITION_MS` 3000, `LIGHT_MAX_HZ` 10).
- Add a short comment file or a `"_doc"` object explaining each key in one line.
- `load_config()` in Python: reads the JSON, then lets environment variables named `GENRATOR_<KEY>` override any key (cast to the default's type).
- `loadConfig()` in JS: fetches `/shared/config.json` once and caches it.

## Acceptance criteria
- [ ] Every C10 key is present in the file.
- [ ] `GENRATOR_HUB_PORT=9000` makes `load_config()["HUB_PORT"] == 9000` (an int, not a string).
- [ ] Calling `loadConfig()` twice performs one fetch.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
