# T104 — Game brain entrypoint (wiring)

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

> **Goal:** The laptop's main game program that starts the audio pipeline, world memory, Gemini loop, reactions and narration modules and connects them to the hub.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Integration & ops | §6 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/brain/__main__.py`, `server/brain/wiring.py`, `tests/brain/test_wiring.py`

## Contracts consumed (stub or fake them in your tests)
C7 (every interface), hub client (T09)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Load config, connect to the hub, create shared objects (AudioInput, ObjectRegistry, RoleMemory, WorldRegistry, ClipStore), start each module's `run(hub, config)`.
- Import modules defensively: if one is missing or crashes, log it, publish `system.health` for it as not ok, and keep the rest running (restart a crashed module after 2 s, max 5 times).
- `--only audio,world` flag to run a subset.

## Acceptance criteria
- [ ] Test with fake modules: one module raising at start doesn't stop the others; the failing one is reported.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
