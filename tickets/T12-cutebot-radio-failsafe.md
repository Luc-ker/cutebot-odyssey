# T12 — Cutebot radio receiver and failsafe stop

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

> **Goal:** The robot listens for commands over micro:bit radio and stops by itself if the gamepad goes quiet, so it never drives off the table on a lost signal.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Robot firmware | §7.1, §7.15 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `firmware/cutebot/main.py` (radio loop and dispatch only), `firmware/cutebot/test_dispatch_host.py`

## Contracts consumed (stub or fake them in your tests)
C6, motors `set_drive`/`stop` (T11), lights `apply(cmd)` (T15), `start_recoil(ms)` (T16) — stub on host

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Configure radio group/channel from constants at the top of the file (same values as `shared/config.json`).
- Main loop: decode packets with the codec (T05 MicroPython copy), dispatch `D` → drive, `L` → lights, `R` → recoil.
- Ignore `D` packets with an older `seq` than the last one (wrap-aware).
- Failsafe: no `D` packet for `FAILSAFE_MS` (default 300 ms) → `stop()`.
- Keep a dispatch function separate from radio I/O so it can be unit-tested on the host with fakes.

## Acceptance criteria
- [ ] Host test: after a `D` packet, then 400 ms of silence, the fake motor receives `stop()`.
- [ ] Host test: out-of-order `seq` is ignored.
- [ ] Manual: switch the gamepad off while driving → robot stops within 0.5 s.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
