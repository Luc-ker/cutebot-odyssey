# T78 — Gemini evaluation harness

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

> **Goal:** Try the world composer on a set of songs and table photos ahead of time, to tune the prompt and catch slow or odd answers before the demo.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | Gemini world composer | §7.6, §14 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `scripts/gemini_eval.py`, `eval/README.md`, `eval/cases.json`

## Contracts consumed (stub or fake them in your tests)
`compose_world` (T71), `guard_world` (T73)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Cases: 8–12 short clips (owned/royalty-free; don't commit copyrighted audio, store paths to local files) × 2 table photos.
- Run each case 3 times; record latency, guard pass rate, chosen setting, role list; write a Markdown report to `eval/report-<date>.md`.
- Flag cases where the same song gives different settings across runs.

## Acceptance criteria
- [ ] Running the script on two cases produces a report with latency and pass rate columns.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
