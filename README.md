# Cutebot Odyssey

> **Every genre generates a world.**

Cutebot Odyssey is a palm-sized robot car you drive around a real table while watching through its eyes, and whatever
music is playing decides which miniature world that table becomes. A phone mounted on an ELECFREAKS Cutebot
streams the robot's view, and an AI video model redraws it live, first person, five centimetres off the ground.
Gemini listens to a few seconds of the music, looks at what the robot sees, and composes a world to match: a sea
shanty floods the table into an ocean, heavy metal turns it into a volcanic wasteland, a lullaby into a snowy
night. Every real object the robot discovers gets a role in that world (the chair becomes a castle) and keeps
it, because the vision service recognises each object again when the robot comes back to it. Hands reaching
into the robot's view become giants. Optional bridge integration lets threats trigger recoil and lights
flash to the beat, and a narrator announces where you've arrived. Change the song and the same table becomes a different world.

Built at **DurHack 2026** for the theme *Composition*: musical composition sets the world, the arrangement of
objects is the level, and the project itself composes a robot, a phone camera, object vision, a multimodal LLM,
a real-time video model and an audio pipeline into one experience.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install ultralytics  # object detection on the laptop
python scripts/launch.py                                # hub + brain + phone vision; no USB bridge
```

Full instructions: [docs/running.md](docs/running.md). Network, HTTPS and phone setup:
[docs/network.md](docs/network.md). Physical build: [docs/build.md](docs/build.md). Demo audio:
[docs/demo-audio.md](docs/demo-audio.md).

Then open the phone page on the phone mounted on the robot and the eye page on the laptop (the launcher prints
both URLs). The eye page passes the phone's frames to the vision service, so it must stay open.

**Current hardware:** two already configured micro:bits, one in the Cutebot and one in the handheld
controller. Leave their independent driving setup alone. The phone **is the only camera**; the laptop does
all processing. NVIDIA Jetson, Arduino, USB camera, Raspberry Pi 5, debug probe and crocodile clips are not
needed. Start with [the phone-as-camera steps](docs/running.md#connect-the-phone-as-the-camera).

The laptop has no robot link by default: camera vision, worlds, screen effects and narration run there,
while physical driving stays independent. Robot commands and sensor telemetry need the optional bridge
integration described in [the running guide](docs/running.md#independent-robot-control).

Tests: `python -m pytest` (Python) and `npm test` (web, Node 22+).

## How it works

```
             ┌──────────── Music (phone, speaker, humming) ────────────┐
             ▼                                                          │
   [Microphone] ──► Audio pipeline (laptop)                             │
                     ├─ Fast layer: beat, tempo, loudness, energy ──────┼──► world pulses (robot lights require optional bridge)
                     └─ Slow layer: 5–10 s audio clip ──┐               │
                                                        ▼               │
   [Phone on Cutebot] ──WebRTC──► Eye page (laptop) ──► Video model (restyled) ──► Robot's-eye screen
                                      │
                                      └─ frames ──► Vision (laptop) ──► World state ──► Gemini (audio + robot's view
                                                    (objects in view,   (roles, IDs,       in, structured world out)
                                                     hands)              in view or not)    │
                                                                                            ├─► World definition + roles
                                                                                            ├─► Restyle prompt ──► Video model
                                                                                            └─► Narration ──► Text-to-speech ──► Speaker

   [Gamepad micro:bit] ──radio──► [Cutebot micro:bit]  (existing independent setup)
```

Three loops run side by side: the **control loop** (gamepad → robot by micro:bit radio, milliseconds, no
network), the **rhythm loop** (beat and energy → screen pulses, local, tens of milliseconds) and the
**world loop** (Gemini recomposes the world every few seconds when the music changes).

| Folder | What |
|---|---|
| `firmware/` | Existing Cutebot/gamepad firmware, plus optional legacy USB bridge and Bluetooth builds |
| `server/` | Python 3.11 asyncio: the hub (WebSocket pub/sub + static files), the brain modules (audio, world memory, Gemini, narration), the serial bridge |
| `vision/` | Vision on the robot's view, run on the laptop: detection, tracking, re-id by appearance, giants, snapshot |
| `web/` | Browser pages, no build step: `phone/`, `eye/`, `sound/`, `status/` |
| `shared/` | Config, roles vocabulary, schemas and fallback worlds read by both sides |
| `docs/` | Runbooks and write-ups. [`genrator-whitepaper.md`](genrator-whitepaper.md) describes the design and current hardware profile |
| `tickets/` | The 111 tickets the build was split into ([components](tickets/Components.md), [contracts](tickets/CONTRACTS.md)) |

## Privacy

No faces are recognised, and no video or audio is kept beyond the short clip each Gemini call needs. A test
enforces both. See [docs/privacy.md](docs/privacy.md).

## Team

| Name | GitHub | Did |
|---|---|---|
| *(add)* | [@Luc-ker](https://github.com/Luc-ker) | |
| *(add)* | | |
| *(add)* | | |
| *(add)* | | |

## AI use

We used AI tools while building Cutebot Odyssey, as the MLH rules require us to disclose. See the
[AI disclosure in docs/devpost.md](docs/devpost.md#ai-use-disclosure). Inside the product, Gemini composes the
worlds and narration, and a real-time video model restyles the robot's view.
