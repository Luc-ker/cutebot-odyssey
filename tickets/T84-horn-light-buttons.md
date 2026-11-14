# T84 — Horn and Light buttons

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

> **Goal:** The Horn button plays a horn that fits the current world (a ship's bell at sea), and the Light button flashes the robot's lights like a lantern.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Narration & sound | §7.1 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/narration/buttons.py`, `tests/narration/test_buttons.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`gamepad.button`, `world.current`, `sfx.play`, `robot.cmd`, `world.event`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `horn` → `sfx.play horn_<setting-key>` choosing the nearest of the 8 settings by keyword, default `horn_kingdom`; publish `world.event horn`.
- `light` → `robot.cmd {kind:"lights", mode:"flash", rgb: warm white, ms: 600}` and `sfx.play whoosh`.
- Cooldown 0.5 s per button.

## Acceptance criteria
- [ ] Horn in a "stormy open ocean" world → `horn_ocean`.
- [ ] Light → one flash command.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
