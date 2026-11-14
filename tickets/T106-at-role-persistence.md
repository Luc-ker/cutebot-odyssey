# T106 — Acceptance test: roles persist

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

> **Goal:** Automated end-to-end check that an object keeps its role when the robot drives away and back, when it's moved, and when it's briefly hidden.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Acceptance tests | §7.4, §12 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `tests/acceptance/test_role_persistence.py`, `tests/acceptance/fakes.py`

## Contracts consumed (stub or fake them in your tests)
C3, C7, hub server (T07), vision replay scenes (T47) or inline fake `vision.state`

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Start the hub and the world modules in-process; feed `vision.state` for a table with a chair; select the `kingdom` fallback world.
- Check the chair's role in `world.objects`; move it; hide it for 2 s; check the role is unchanged.
- `fakes.py`: fake Gemini, fake snapshot server, fake audio source; other acceptance tests may import it once merged.

## Acceptance criteria
- [ ] Test passes when the system works and fails if `RoleMemory` is replaced by a stub that forgets.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
