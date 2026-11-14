# T74 — World scheduler and change decision

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

> **Goal:** The world loop: every few seconds (or right after a song change) ask Gemini what world the music implies, and switch worlds only when it's clearly different; reuse remembered worlds for returning songs; hold the current world on any failure.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Gemini world composer | §6, §7.6, §7.7, §7.12, §7.15 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/gemini/scheduler.py`, `tests/gemini/test_scheduler.py`

## Contracts consumed (stub or fake them in your tests)
C3 (`audio.features`, `world.current`, `world.event`, `world.select`), C7 (`ClipStore`, `ChangeDetector`, `signature`/`distance`, `WorldRegistry`, `RoleMemory`, `ObjectRegistry`, `compose_world`, `guard_world`, `load_fallback_worlds`), snapshot HTTP (C8)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Tick every `GEMINI_INTERVAL_S`, or on a change-detector hit (min 4 s apart); skip while silent or while a call is in flight.
- Before calling Gemini: compute the signature; if `WorldRegistry.match` finds a stored world different from the current one, adopt it at once (`returning: true`).
- Otherwise call Gemini, guard, then adopt if there's no world yet, or if the signature distance from the current world's signature > `WORLD_CHANGE_THRESHOLD` and the setting differs.
- On adopt: assign id + signature, register, write roles to `RoleMemory`, publish `world.current` and `world_changed`.
- Any failure → keep the current world, log, publish `system.health ok:false` briefly.
- `world.select {name}` adopts a fallback world immediately (T75); start-up uses the `kingdom` fallback.
- Re-publish `world.current` every 5 s for late joiners.

## Acceptance criteria
- [ ] With fakes: first good response adopts a world; a similar second response does not; a very different one does.
- [ ] Gemini timeout → no `world.current` change.
- [ ] Returning signature → stored world re-adopted without calling Gemini.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
