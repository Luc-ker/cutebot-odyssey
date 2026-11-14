# T49 — Per-world role memory

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

> **Goal:** Remember which role every object has in every world, so the chair is the castle every time you drive past it, and is the castle again when an earlier song comes back.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | World memory & game logic | §7.4, §7.12 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/memory.py`, `tests/world/test_memory.py`

## Contracts consumed (stub or fake them in your tests)
C7 (`RoleMemory`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `get`, `set`, `roles_for(world_id)`, `forget_object(obj_id)`.
- Roles stored as `{role, name, behaviour}` keyed by world id then object id.
- Keep a session-only store in memory; optional JSON snapshot to `runtime/memory.json` for crash recovery (git-ignored), cleared on `system.reset`.
- Two objects in the same world may share a role but not a name; `set` appends " II" if a name is already taken.

## Acceptance criteria
- [ ] Set chair=castle in world A, then roles in world B, then `get(A, chair)` → castle.
- [ ] Name clash gets a suffix.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
