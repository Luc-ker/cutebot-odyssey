# T38 — Object detector

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

> **Goal:** Find the everyday objects on the table (cups, bottles, books, bags, laptops, phones, chairs) in each overhead frame so they can become castles, ships and dragons.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Overhead vision | §7.3 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `jetson/detector.py`, `jetson/tests/test_detector.py`

## Contracts consumed (stub or fake them in your tests)
C8 (`detect`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Load a small YOLO model (TensorRT engine if present from T46, else PyTorch/ONNX); filter to useful COCO classes (cup, bottle, book, backpack, handbag, laptop, cell phone, chair, bowl, scissors, teddy bear, remote, mouse, keyboard...).
- Confidence threshold and minimum box size from constants; ignore boxes outside the table (via calibration).
- Return `Detection` list in pixel space.

## Acceptance criteria
- [ ] Test with a stored sample image of a table with known items: expected classes found (marked as a slow test).
- [ ] Detections fully outside the table polygon are dropped.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
