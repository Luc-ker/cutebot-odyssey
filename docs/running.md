# Running Genrator (laptop side)

One command starts the hub, the game brain, the serial bridge and the vision service; Ctrl-C stops all of
them. Everything runs on the laptop. The only other devices are the phone on the robot, the micro:bits and
the speaker.

## First time on a laptop

```bash
git clone https://github.com/Luc-ker/sonar-bot-tune.git
cd sonar-bot-tune
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt sounddevice pyserial ultralytics
export GEMINI_API_KEY=...        # PowerShell: $env:GEMINI_API_KEY = "..."
```

Python 3.11 or newer. Node 22+ is only needed to run the web tests (`npm test`). `ultralytics` (with PyTorch) is
the object detector; the first run downloads `yolo11n.pt` into `vision/models/`, so start it once on good wifi
before the demo. Without it, vision still runs (giants, snapshots) but finds no objects.

## Start

```bash
python scripts/launch.py                          # hub + brain + serial bridge + vision, live microphone
python scripts/launch.py --replay drive_around    # a recorded robot's-view scene instead of live vision (T47)
python scripts/launch.py --audio-file song.wav    # feed a file into the audio pipeline instead of the mic
python scripts/launch.py --no-bridge              # no USB micro:bit plugged in
python scripts/launch.py --vision-camera 0        # vision from a webcam on the laptop instead of the phone
```

| Service | Command the launcher runs | Healthy when |
|---|---|---|
| `[hub]` | `python -m server.hub` | `system.health {service: "hub", ok: true}` |
| `[brain]` | `python -m server.brain --skip bridge` | `system.health {service: "brain"}` (each module also reports `brain.<name>`) |
| `[bridge]` | `python -m server.brain --only bridge` | `system.health {service: "serial_bridge", ok: true}`: needs the bridge micro:bit on USB |
| `[vision]` | `python -m vision` | `system.health {service: "vision", ok: true}`: needs the phone streaming and the eye page open (not waited for) |
| `[vision]` | `python scripts/vision_replay.py <scene> --loop` (with `--replay`, instead) | the first `vision.state` arrives |

The launcher waits up to 20 s (`--timeout`) for every service except live vision, prints a health table and
the page URLs,
then streams every service's log with its prefix. Services that are not healthy are listed, but nothing
is stopped: the demo degrades gracefully (whitepaper §7.15).

Pages, served by the hub (use the laptop's LAN address the launcher prints, not `localhost`, on other devices):

| Page | Open on | Path |
|---|---|---|
| Robot's-eye view | main screen; **keep it open**, it feeds the phone's frames to vision | `/eye/` |
| Controller (joystick over Bluetooth) | the player's phone, Chrome on Android; see `firmware/makecode/README.md` | `/pad/` |
| Sound (narrator and effects) | laptop with the speaker; click **Start sound** | `/sound/` |
| Status and control | team laptop | `/status/` |
| Phone camera | the phone on the robot (needs HTTPS, see `docs/network.md`) | `/phone/` |

## Running parts by hand

```bash
python -m server.hub
python -m server.brain --list                     # every module and its group
python -m server.brain --only audio,world         # a subset (groups or module names)
python -m server.brain --only bridge              # the serial bridge alone
python -m vision                                  # vision on the phone's frames (via the eye page)
python -m vision --camera 0                       # vision on a laptop webcam, to test without the robot
python scripts/reset_demo.py                      # full demo reset
```

Environment overrides: any config key as `GENRATOR_<KEY>` (for example `GENRATOR_AUDIO_DEVICE=2`),
`GENRATOR_SERIAL_PORT=COM5`, `GENRATOR_AUDIO_FILE=song.wav`, `GENRATOR_LOG_LEVEL=DEBUG`.

## How the brain copes with missing pieces

`server/brain/wiring.py` imports each module on its own. A module that is not merged yet or whose
dependency is missing is reported `ok: false, detail: "missing: ..."` and skipped. A module whose `run`
raises loses its subscriptions and is restarted after 2 s, at most 5 times. Everything else keeps running.
The status page shows every `brain.<module>` line.

## Manual check (T96 acceptance)

On a fresh clone, after the install steps above:

1. `python scripts/launch.py --replay drive_around --no-bridge`
2. Within 20 s the table shows `OK  hub`, `OK  brain` and `OK  vision`, then `All services healthy after N s`.
3. Open `/status/` from the printed URLs: hub, brain and the brain modules are listed, and `vision.state` shows ~10 msg/s.
4. Press Ctrl-C: the launcher prints `[launch]  all stopped.`, and no Python process from Genrator is left running.

Result on 2026-11-14 (Windows 11, no micro:bit, `--no-bridge`, T47 not merged yet so no `--replay`):
`OK hub`, `OK brain` after **2.2 s**. `brain.beat` and `brain.features` were not ok on a machine without
a microphone (no input device), and `brain.scheduler` reported `missing` because T74 was not merged.
Re-run with `--replay` once T47 lands.

## Troubleshooting

- **`no micro:bit serial port found`**: plug the bridge micro:bit in, or set `GENRATOR_SERIAL_PORT`. `--no-bridge` skips it.
- **`brain.beat` / `brain.features` not ok**: no microphone. Run `python scripts/list_audio_devices.py`, then set `GENRATOR_AUDIO_DEVICE`.
- **Port 8765 in use**: a previous run is still alive. Close it, or set `GENRATOR_HUB_PORT`.
- **Phone camera shows nothing**: the phone page needs HTTPS. Follow `docs/network.md`.
- **No objects named in the HUD**: on the status page, the `vision` service should be ok and `vision.state`
  should arrive at ~10 msg/s. (`camera.frame` never shows there: the hub only sends frames to the vision service.)
  If vision says "no camera frames", the eye page is closed or the phone isn't streaming. If it says "no object
  detection", install `ultralytics`.
