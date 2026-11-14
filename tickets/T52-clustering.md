# T52 — Object clustering into places

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

> **Goal:** Read several objects sitting close together as one place in the world (three cups become a village).

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | World memory & game logic | §7.5 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `server/world/clusters.py`, `tests/world/test_clusters.py`

## Contracts consumed (stub or fake them in your tests)
C7 (`find_clusters`)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Single-linkage grouping with gap `CLUSTER_GAP`; clusters need ≥ 3 members.
- Cluster id stable while membership overlaps by > 50 % (keep a small history).
- Cluster role chosen from place roles (village, market, harbour, camp) using world setting; name from templates.

## Acceptance criteria
- [ ] Three objects 3 cm apart and one far away → one cluster of three.
- [ ] Moving one member slightly keeps the same cluster id.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
