# T03 — Roles vocabulary data file

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

> **Goal:** The fixed list of roles Gemini is allowed to give objects, each with its icon, behaviour, sound and a phrase for the video prompt.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Foundation | §8 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `shared/roles.json`, `tests/common/test_roles.py`

## Contracts consumed (stub or fake them in your tests)
C5

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- Fill `shared/roles.json` with every role in §8 (castle, palace, fortress, temple, skyscraper, tower, watchtower, lighthouse, beacon, village, market, harbour, camp, ship, raft, boat, forest, grove, jungle_patch, mountain, volcano, cliff, glacier, river, bridge, road, treasure, relic, crystal, dragon, sea_serpent, lava_beast, yeti, robot_sentinel, giant) plus ~10 more that fit the §7.6 world table (docking_tower, subway, catacombs, ruin, den...).
- For each: `behaviour`, `icon` (file stem for T88), `sfx`, `prompt` phrase, `worlds` (setting keywords), `classes` (detector classes it suits, used by T51).
- `giant` gets `"system_only": true`.

## Acceptance criteria
- [ ] Test loads the file: every role unique, every behaviour in the enum, every role has non-empty `prompt` and `icon`.
- [ ] At least 4 `threat` roles and every §7.6 example world has at least 5 roles listing it.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
