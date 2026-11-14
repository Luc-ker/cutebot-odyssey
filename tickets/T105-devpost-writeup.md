# T105 — Devpost write-up, README and AI disclosure

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

> **Goal:** Explain Genrator clearly for judges and the submission: what it does, how it fits "Composition", how it's built, and how AI tools were used.

| Priority | Component | Whitepaper |
|---|---|---|
| P1: important polish | Integration & ops | §1, §3, §11, §13 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `README.md`, `docs/devpost.md`

## Contracts consumed (stub or fake them in your tests)
Nothing from other tickets.

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- README: one-paragraph pitch, how to run (link `docs/running.md`), architecture diagram from §6, team.
- Devpost text: inspiration, what it does, how we built it, challenges, accomplishments, what we learned, what's next (from §15), prize tracks (§13).
- AI use disclosure as required by MLH rules.

## Acceptance criteria
- [ ] README renders on GitHub with working links; Devpost draft covers every required section.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
