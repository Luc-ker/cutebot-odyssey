# T46 — TensorRT export and FPS benchmark

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

> **Goal:** Make object detection fast enough on the Jetson Orin Nano by converting the model to TensorRT and measuring frame rate.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | Overhead vision | §10 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `scripts/jetson_export.sh`, `scripts/jetson_bench.py`, `docs/jetson-setup.md`

## Contracts consumed (stub or fake them in your tests)
Nothing from other tickets.

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Script to export the chosen YOLO model to a TensorRT engine (FP16) on the Jetson.
- Bench: fps for PyTorch vs engine at 640 and 960 input sizes, with tracker on.
- `docs/jetson-setup.md`: JetPack version, Python packages, camera permissions, how to run `jetson/main.py` on boot.

## Acceptance criteria
- [ ] Doc includes measured fps and the chosen input size; engine path matches what T38 loads.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
