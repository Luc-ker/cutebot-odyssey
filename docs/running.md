# Running Genrator: laptop and phone camera

The two existing micro:bits (one in the Cutebot, one in the handheld gamepad) handle driving independently.
Leave that working setup as it is. The phone **is the camera**: its rear camera streams from the browser to
the laptop, which runs all vision, audio and world logic. No separate camera or onboard computer is needed.

## Install on the laptop

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install ultralytics                  # object detection; downloads model on first run
pip install google-genai                 # optional Gemini world composition
cp .env.example .env                    # Windows: copy .env.example .env
# Edit .env and fill in GEMINI_API_KEY=your_key_here
```

The app automatically loads `.env` from the repository root. Existing environment variables take
precedence. Keep the key in your local `.env` (ignored by Git); `.env.example` contains no key. Restart
the launcher after editing `.env`. The first valid Gemini world replaces the startup Kingdom fallback;
subsequent calls keep the current world when the music has not meaningfully changed. The default model
is `gemini-3.8-flash` with low thinking and a 30-second per-attempt timeout; override the model or timeout
with `GENRATOR_GEMINI_MODEL` / `GENRATOR_GEMINI_TIMEOUT_S` if needed. Requests run one at a time per world
scheduler, so a slow call delays the next one.

Python 3.11+; Node 22+ is only needed for `npm test`. Without `ultralytics`, vision can still provide
snapshots and heuristic hand detection but does not detect objects. Start it once on good internet to cache
the model in `vision/models/`. Gemini and AI restyling need internet/provider configuration; the raw phone
view and local vision do not. Without a Gemini key, use fallback worlds on `/status/`.

## Connect the phone as the camera

1. Connect phone and laptop to the same Wi-Fi or hotspot, with device-to-device traffic allowed.
2. Follow [the HTTPS setup](network.md#2-https-certificate-the-phone-camera-needs-it). In the same terminal,
   set the printed `GENRATOR_TLS_CERT`, `GENRATOR_TLS_KEY` and `GENRATOR_TLS_CA` values. Install/trust the public
   CA certificate on the phone. Do this again if the laptop IP changes (phone CA trust is only needed once).
3. Start `python scripts/launch.py`. It starts **hub + brain + vision**, without a USB bridge.
4. Open the printed `https://<laptop-IP>:8765/eye/` URL on the laptop and keep it visible.
5. On the phone, open the printed `https://<laptop-IP>:8765/phone/` URL in Safari on iPhone or Chrome on
   Android. Allow camera access. The page prefers 16:9 landscape from the rear camera. Turn the phone
   sideways; on iPhone, turn off **Portrait Orientation Lock** in Control Centre. Safari may not allow a
   website to force rotation, so the page shows a hint while held upright. Point the rear camera forward
   from the Cutebot mount. Refresh `/phone/` after updating to load the new layout.
6. Keep the phone page visible, screen unlocked, and wait for **STREAMING**. The laptop eye page should show
   exactly what the phone sees. No camera app, video cable, Bluetooth connection or third micro:bit is needed.
7. Open `/sound/` on the laptop and click **Start sound**. On `/status/`, check that `vision.state` arrives
   and put an object in front of the phone to check the HUD.

The video route is **phone rear camera → WebRTC → laptop eye page → vision service on the laptop**.
The eye page must stay open because it forwards frames to vision. See [the physical mount](build.md).

## Commands and pages

```bash
python scripts/launch.py                         # normal two-micro:bit + phone build
python scripts/launch.py --no-music              # initial Kingdom run: camera/objects, no microphone
python scripts/launch.py --replay drive_around   # simulated vision for development
python scripts/launch.py --audio-file song.wav   # audio file instead of laptop microphone
python scripts/launch.py --no-vision              # laptop services without vision
```

| Page | Device | Path |
|---|---|---|
| Phone camera | phone on the robot, foreground and unlocked | `/phone/` |
| Robot's-eye view | laptop; keep visible to feed vision | `/eye/` |
| Narration and effects | laptop; click Start sound | `/sound/` |
| Health, reset and fallback worlds | laptop | `/status/` |

`/pad/` and `firmware/makecode/` are an alternate Bluetooth build, not part of this setup. Do not replace
your working gamepad firmware to connect the camera.

| Service | Command | Healthy when |
|---|---|---|
| hub | `python -m server.hub` | `system.health`, service `hub`, ok |
| brain | `python -m server.brain --skip bridge` | service `brain`; individual modules also report health |
| vision | `python -m vision` | receiving frames from phone through eye page |

The launcher waits up to 20 seconds for hub and brain. Live vision waits for the browser pages to connect,
so it is not part of that initial health wait. Ctrl-C stops the launcher and all its services.
Environment overrides use `GENRATOR_<KEY>`, for example `GENRATOR_AUDIO_DEVICE=2` or `GENRATOR_HUB_PORT=8766`.

For an initial run without music, use `--no-music`. The scene starts in Kingdom; live camera, object
roles and narration remain available. The microphone and audio modules are off, and music cannot change
the world. The status page can still select other fallback worlds or reset to Kingdom. Object role
assignment may use Gemini; local role assignment takes over if it is unavailable. Restart without
`--no-music` when ready to test music-driven composition.

**Stable Kingdom mode** (`STABLE_KINGDOM_ENABLED`, on by default for the demo) keeps the rendered scene
steady. The renderer gets one fixed miniature-world prompt (`STABLE_KINGDOM_PROMPT`: the camera is a tiny
explorer, bottles become watchtowers and laptops fortress walls, under the desk is a cave, a gigantic
castle stands in the far distance) and nothing else ever changes it: no per-object, giant or world-transition prompts, and
`world.select` is ignored. A new object must stay in view for `OBJECT_SETTLE_S` (1 s) before it gets a
role, and its role is chosen locally by detector class, so every bottle is the same watchtower and no
Gemini role call is made. Hands and people over the table no longer trigger giant events. The microphone
stays off. Set `GENRATOR_STABLE_KINGDOM_ENABLED=false` to get the dynamic game back. Some flicker can
remain because the video model redraws moving frames.

For actual AI video transformation rather than the offline tint preview, configure Decart as described
in [the restyle provider setup](restyle-provider.md). It also works with `--no-music`.

## Independent robot control

Driving and the robot's existing onboard behavior belong to your already configured micro:bits. The laptop
has no robot connection by default. Camera vision, worlds, screen beat effects and narration work normally;
laptop-generated `robot.cmd` messages do not reach the robot, and gamepad buttons and ultrasonic telemetry
do not reach the laptop. Distance is unknown there; visual proximity still uses object size in the view.

The old serial bridge code is retained as an **optional integration** for a future build with extra bridge
hardware/firmware: `pip install pyserial`, then `python scripts/launch.py --bridge`. It is not required or
started for this build. `--no-bridge` remains accepted for older commands and is now the default.
Do not repurpose either of the two working boards as a bridge.

## Troubleshooting and checks

- **Phone page says Needs HTTPS:** follow [network.md](network.md); `localhost` on the phone refers to the
  phone, so use the laptop's LAN IP, not localhost. Trust the certificate before granting camera permission.
- **Phone cannot reach laptop:** check hotspot/client isolation and firewall; both devices must share a local
  network. WebRTC also needs peer traffic, not just access to the hub's TCP port.
- **Eye page has no video:** keep both browser pages visible and the phone unlocked. Reload the eye page,
  then the phone page; check camera permission and the phone's rear-camera preview.
- **Vision says no camera frames:** keep `/eye/` open. The phone does not send JPEGs directly to Python.
- **No object detection:** install `ultralytics`; confirm the model finished downloading.
- **Python reports CERTIFICATE_VERIFY_FAILED:** set `GENRATOR_TLS_CA` to the public `rootCA.pem` printed by
  `make_cert.sh` in the launcher terminal. Restart the launcher.
- **No microphone:** run `python scripts/list_audio_devices.py` and set `GENRATOR_AUDIO_DEVICE`, or use
  `--audio-file song.wav`.
- **No robot telemetry/serial bridge health:** expected with the independent two-board setup.

Software checks: `python -m pytest -q`, `npm test`, and
`python scripts/launch.py --replay drive_around` for a hardware-free service startup check.
Physical camera streaming and existing driving must be checked on your devices.
