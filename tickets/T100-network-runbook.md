# T100 — Network runbook

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

> **Goal:** Step-by-step instructions to get the laptop, phone and Jetson talking on the day, including the HTTPS certificate the phone camera needs and what to do if venue wifi fails.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Integration & ops | §7.15, §14 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `docs/network.md`, `scripts/make_cert.sh`

## Contracts consumed (stub or fake them in your tests)
Nothing from other tickets.

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Recommended setup: a laptop or phone hotspot, fixed IPs or hostnames for the laptop and Jetson.
- `make_cert.sh`: create a local CA/certificate (e.g. with mkcert) for the laptop IP; how to trust it on the phone; set `TLS_CERT`/`TLS_KEY`.
- Ports to open; a checklist to verify each link; what still works without internet (driving, beat effects, fallback worlds).

## Acceptance criteria
- [ ] A teammate who didn't write it can follow the doc to get the phone streaming to the eye page.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
