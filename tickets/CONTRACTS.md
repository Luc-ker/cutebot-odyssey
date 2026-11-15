# Shared contracts — Genrator

> **Current hardware profile (2026-11-14):** two already configured micro:bits in Cutebot and handheld
> gamepad handle driving independently. The phone itself is the only camera; laptop runs all compute.
> No Jetson, Arduino, USB camera, Raspberry Pi 5, debug probe or crocodile clips are required.
> USB bridge is optional (`launch.py --bridge`), off by default. No firmware changes are required for
> camera streaming. Historical ticket instructions about removed hardware are superseded by
> [the running guide](../docs/running.md) and [build guide](../docs/build.md).


Source of truth for behaviour: `genrator-whitepaper.md` (§ numbers in tickets refer to it).
One file = one ticket. Grouping by component: `tickets/Components.md`. Tickets are **not assigned**.

> **Change (T111): first person only.** There is no overhead camera, no Jetson and no map. The only camera is
> the phone on the robot. Vision runs on the laptop on the phone's frames, every position is in **view units**
> (C1), objects that leave the view are remembered, and the robot has no position or heading. Tickets written
> before this change (T36–T46, T85–T94 and parts of others) describe the old design; where they disagree with
> this page, this page wins. See `tickets/T111-first-person-vision.md`.

## How these tickets stay independent

Every ticket **owns its own files** and nothing else. Where a ticket needs another ticket's code, it codes
against the **contracts on this page** and uses a small local stub or fake in its own tests until the real
module lands. No ticket has to wait for another ticket to start, build or test its work.
The acceptance tests (T106–T109) are written against these contracts and go green once the pieces merge.

Changing a contract on this page is its own small PR that the owners of the affected tickets review.

## Assumed layout and stack

```
shared/          config.json, roles.json, schemas/*.json, worlds/*.json       (data both sides read)
firmware/        MicroPython for micro:bit V2: cutebot/, gamepad/, bridge/, common/
server/          Python 3.11, asyncio. hub/, common/, bridge/, audio/, world/, gemini/, narration/, ops/
web/             Plain JavaScript ES modules, no build step. common/, phone/, eye/, sound/, status/
vision/          Python 3 vision on the phone's frames, run on the laptop (OpenCV, a YOLO model)
scripts/         Launchers, benches, test tools
tests/           pytest for server/ (mirrors source paths; vision/tests/ for vision/); web tests use `node --test`
docs/            Runbooks and write-ups
```

Firmware can move to MakeCode if the team prefers; the radio packets (C6) stay the same.

## C1. Space and time

- **View coordinates:** `[x, y]`, floats, normalised to the robot camera's frame: `0 ≤ x ≤ 1` left to right,
  `0 ≤ y ≤ 1` top to bottom. `x = 0.5` is straight ahead; the angle to an object is
  `geometry.bearing(x, config.CAMERA_HFOV_DEG)`.
- **Sizes:** `[w, h]` as fractions of the frame's width and height. Bigger means closer; "size" alone means
  `max(w, h)` (`geometry.view_size`).
- **No robot pose.** The camera is the robot, so there is no position or heading on the table. Distance ahead
  comes from the ultrasonic sensor (`robot.telemetry.distance_cm`).
- **Time:** `ts` is Unix seconds as a float, from the sender's clock.
- **IDs:** objects have integer `id`s from the vision tracker, kept across leaving and re-entering the view by
  appearance re-id. Worlds have string `id`s (`"w-" + 8 hex`). Giants have string ids `"g<n>"`.

## C2. The hub (WebSocket pub/sub on the laptop)

- URL: `ws(s)://<laptop>:<config.HUB_PORT>/hub`. The same server serves `web/` and `shared/` as static files.
- Every message is an **envelope**: `{"topic": str, "ts": float, "src": str, "data": object}`.
- Client → hub: `{"op": "sub", "topics": ["vision.*", "audio.beat"]}` (a trailing `*` is a prefix match),
  `{"op": "pub", "topic": ..., "ts": ..., "src": ..., "data": ...}`.
- Hub → client: the envelope as published. The hub never changes `data`.
- Python client (T09): `hub = await HubClient.connect(url, src)`, `await hub.pub(topic, data)`,
  `hub.sub(pattern, async_callback(envelope))`.
- JS client (T08): `const hub = await connectHub(url, src)`, `hub.pub(topic, data)`,
  `hub.sub(pattern, envelope => ...)`, `hub.onStatus(s => ...)` with `s` in `"open" | "closed"`.

## C3. Topics and their `data`

| Topic | Publisher | `data` |
|---|---|---|
| `camera.frame` | eye page (`web/eye/frames.js`), `VISION_HZ` | `{jpeg, w, h}`: the phone's raw view as base64 JPEG, `FRAME_WIDTH` px wide. **Bulk:** only delivered to clients that subscribe by a pattern naming it (`camera.frame`, `camera.*`), never to `*` |
| `vision.state` | vision service (`python -m vision`, T44), up to `VISION_HZ` | `{frame_ts, objects:[{id, cls, pos, size, conf}], giants:[{id, kind:"hand"\|"person", pos, size, edge:"top"\|"bottom"\|"left"\|"right"}]}`: only what is in view now |
| `robot.telemetry` | serial bridge (T22) | `{distance_cm, line:[l, r], override: bool}` |
| `robot.cmd` | light director (T23), threat reaction (T58), reset (T63) | `{kind:"lights", mode:"solid"\|"flash"\|"pulse", rgb:[r,g,b], ms}` or `{kind:"recoil", ms}` or `{kind:"rumble", ms}` |
| `gamepad.button` | serial bridge (T22) | `{button: "light"\|"horn"\|"shout"\|"reset"}` |
| `audio.beat` | beat tracker (T65) | `{tempo_bpm, strength}` (0–1) |
| `audio.features` | features (T66), 20 Hz | `{rms, energy, brightness, silent: bool}` (energy, brightness 0–1) |
| `world.current` | world scheduler (T74) | `{world: World, previous_id: str\|null}` — sent on change and every 5 s |
| `world.transition` | transition coordinator (T95) | `{from: World\|null, to: World, started, duration_ms}` |
| `world.composing` | world scheduler (T74) | `{state: "composing"\|"done"\|"kept"\|"failed"\|"quiet", name?}` — music-driven composition progress for the eye HUD: `composing` once a music clip goes to Gemini, then `done` (new or returning world, `name`), `kept` (too similar, current world kept) or `failed`; `quiet` when a listening window heard no music |
| `world.objects` | world objects publisher (T62), 10 Hz | `{world_id, objects:[{id, cls, pos, size, visible, role, name, behaviour, cluster_id, from_sky}], clusters:[{id, pos, size, member_ids, role, name}], terrain:{open_space, under_table}}`: every object discovered and not yet forgotten; `visible` false = out of view (pos/size are where it was last seen) |
| `robot.state` | robot state aggregator (T55), 10 Hz | `{distance_cm, override, facing_id: int\|null}` |
| `world.event` | various (see `kind`) | `{kind, ...}` — kinds listed below |
| `narration.say` | anyone | `{text, priority: 0–3, voice?: str}` (3 = most urgent) |
| `narration.speak` | narration queue (T79) | `{id, text, voice}` — exactly one at a time |
| `narration.done` | TTS (T80) | `{id}` |
| `sfx.play` | anyone | `{sound: str}` — names from `roles.json` `sfx` plus `warning`, `landing`, `chime`, `whoosh`, `horn_<setting>` |
| `video.prompt` | prompt composer (T29) / blender (T30) | `{prompt}` |
| `video.status` | eye page (T31) | `{mode:"restyled"\|"raw", latency_ms}` |
| `webrtc.signal` | phone (T25) / eye receiver (T26) | `{to, from, sdp?, candidate?}` |
| `system.health` | every service, every 2 s | `{service, ok: bool, detail}` |
| `system.reset` | reset (T63), status page (T97) | `{}` — **every stateful module clears its state when it sees this** |
| `world.select` | status page (T97), reset (T63) | `{name}` — adopt a pre-composed fallback world by name (T74) |
| `show.set` | eye page buttons (show / listen) | `{running?: bool, listening?: bool}` — start/stop the show (AI video); `listening: true` listens to the song for one window (`CLIP_SECONDS`) and changes the scene once, `false` cancels |
| `show.state` | world scheduler (T74) | `{running, listening, can_listen}` — sent on every `show.set`, when a listening window ends and every 5 s; `listening` is true only while a window is open; `can_listen` false when there is no microphone (stable mode, music off) |

`world.event` kinds:
`object_added {id, role, name, behaviour, announce, from_sky}`, `object_removed {id}`,
`giant_enter {id, kind, edge}`, `giant_leave {id}`, `danger_enter {id, name, role}`, `danger_exit {id}`,
`friendly_enter {id, name, role}`, `blocked {obstacle}`, `world_changed {world_id, returning: bool}`,
`horn {}`, `shout {facing_id}`.

## C4. World (whitepaper §7.7 plus two fields)

```json
{ "id": "w-1a2b3c4d",
  "world": {"name", "setting", "mood", "time_of_day", "weather", "palette": [str, str, str]},
  "roles": [{"object_id": int, "role": str, "name": str, "behaviour": "friendly"|"neutral"|"threat"}],
  "terrain": {"open_space": str, "under_table": str},
  "restyle_prompt": str, "narration": str,
  "music_signature": {"tempo_bpm": float, "energy": float, "brightness": float, "chroma": [12 floats]} }
```
JSON Schema file: `shared/schemas/world.schema.json` (T02). `palette` entries are colour words; `shared/colours.json`
(T02) maps common colour words to RGB for the robot's lights and screen tints.

## C5. Role vocabulary — `shared/roles.json` (T03)

`[{"role": "castle", "behaviour": "neutral", "icon": "castle", "sfx": "bell", "prompt": "a stone castle tower",
"worlds": ["kingdom", ...], "classes": ["chair", ...]}]`. Roles follow whitepaper §8. `giant` exists but is
system-only. Until T03 merges, tests use a three-role stub.

## C6. micro:bit radio and serial

- Radio group `config.RADIO_GROUP`, channel `config.RADIO_CHANNEL`, ASCII packets ≤ 32 bytes, fields comma-separated.

| Packet | Direction | Meaning |
|---|---|---|
| `D,<throttle>,<turn>,<seq>` | gamepad → Cutebot | drive; throttle and turn are ints −100..100; seq 0–255 wraps |
| `B,<L\|H\|S\|R>` | gamepad → bridge | button: Light, Horn, Shout, Reset |
| `L,<S\|F\|P>,<r>,<g>,<b>,<ms>` | bridge → Cutebot | lights: Solid, Flash, Pulse; 0–255 colours |
| `R,<ms>` | bridge → Cutebot | recoil (reverse then turn), overrides the joystick for `ms` |
| `V,<ms>` | bridge → gamepad | rumble |
| `T,<dist_cm>,<lineL>,<lineR>,<override>` | Cutebot → bridge | telemetry; line 0/1, override 0/1, 10 Hz |

- Bridge ↔ laptop serial: the same strings, newline-terminated, 115200 baud.
- Python codec: `server/common/radio_codec.py` `encode(dict) -> str`, `decode(str) -> dict|None` (T05).

## C7. In-process Python interfaces (laptop "brain" process)

| Module (owner) | Interface |
|---|---|
| `server/common/config.py` (T01) | `load_config() -> dict` |
| `server/common/geometry.py` (T06) | `dist(a,b)`, `angle_to(a,b)`, `angle_diff(a,b)`, `wrap_angle(a)`, `bearing(x, hfov_deg)`, `view_size(size)` |
| `server/common/schemas.py` (T02, T04) | `validate_world(obj) -> list[str]` errors, `validate_envelope(obj) -> list[str]` |
| `server/world/registry.py` (T48) | `ObjectRegistry.update(vision_state, now) -> Diff{added, removed}`; `.get(id)`; `.all()`; `.visible()`. Out of view after `VIEW_GRACE_S`, removed after `OBJECT_FORGET_S` |
| `server/world/memory.py` (T49) | `RoleMemory.get(world_id, obj_id) -> Role\|None`, `.set(world_id, obj_id, role)`, `.roles_for(world_id)` |
| `server/world/fallback_roles.py` (T51) | `pick_role(world, cls, taken_roles) -> Role` |
| `server/world/clusters.py` (T52) | `find_clusters(objects_in_view, max_gap) -> list[Cluster{id, member_ids, pos, size}]` |
| `server/world/terrain.py` (T53) | `analyse(objects, world) -> {"open_space": str, "under_table": str}` |
| `server/world/worlds.py` (T54) | `WorldRegistry.add(world)`, `.match(signature) -> World\|None`, `.get(id)` |
| `server/audio/capture.py` (T64) | `AudioInput(config).start()`, `.on_block(cb(samples_float32, ts))`, `.last(seconds) -> ndarray`, `.rate` |
| `server/audio/silence.py` (T67) | `SilenceGate().update(rms, ts) -> bool` (true = silent) |
| `server/audio/change.py` (T69) | `ChangeDetector().update(samples, ts) -> bool` (true once per detected song change) |
| `server/world/facing.py` (T56) | `facing(objects, clusters=None) -> int\|None`: the biggest in-view object within `FACING_HALF_ANGLE_DEG` of straight ahead |
| `server/audio/clips.py` (T68) | `ClipStore(audio_input).get_clip(seconds) -> bytes\|None` (16 kHz mono WAV; None if mostly silent) |
| `server/audio/signature.py` (T70) | `signature(window) -> dict`, `distance(sig_a, sig_b) -> float` 0–1 |
| `server/gemini/client.py` (T71) | `async compose_world(audio_wav, image_jpeg, objects, current_world) -> dict` (raw); `async ask_json(parts, schema) -> dict` |
| `server/gemini/prompt.py` (T72) | `build_compose_parts(audio_wav, image_jpeg, objects, current_world, vocab) -> list` |
| `server/gemini/guard.py` (T73) | `guard_world(raw, object_ids, vocab) -> World\|None` |
| `server/gemini/object_role.py` (T76) | `async request_role(world, obj, image_jpeg) -> {role, name, behaviour, announce}\|None` |
| `server/world/fallback_worlds.py` (T75) | `load_fallback_worlds() -> list[World]` |

Every brain module exposes `async def run(hub, config)` if it has its own loop; T104 wires them.

## C8. Vision interfaces (`vision/`, runs on the laptop)

| Module (owner) | Interface |
|---|---|
| `frames.py` (T111) | `HubFrames()`; `.on_envelope(env)` for `camera.frame`; `.read(timeout) -> (ts, frame_bgr)`, `.latest()` |
| `camera.py` (T36) | `Camera(config, index=, file=)`: same interface, a local camera or clip (development) |
| `detector.py` (T38) | `Detector().detect(frame) -> list[Detection{bbox:[x1,y1,x2,y2], cls, conf}]`, `.detect_all(frame)` |
| `tracker.py` (T39) | `Tracker(min_hits=).update(dets, ts) -> list[Track{id, cls, bbox, conf}]` |
| `reid.py` (T40) | `ReId(config).apply(tracks, ts, frame) -> list[Track]`: stable ids by appearance for `OBJECT_FORGET_S` |
| `giants.py` (T43) | `GiantDetector().detect(frame, persons) -> list[{bbox, kind, edge}]`: skin blobs reaching in from a frame edge, and person detections |
| `state.py` (T44) | `build_state(tracks, giants, frame_shape, ts) -> vision.state data` |
| HTTP `GET <VISION_HOST>:<VISION_HTTP_PORT>/snapshot.jpg` (T45) | the robot's current view, people blurred, max 1024 px wide |

## C9. Browser interfaces (`web/`)

| Module (owner) | Interface |
|---|---|
| `web/common/hub.js` (T08) | see C2 |
| `web/common/config.js` (T01) | `await loadConfig() -> object` |
| `web/common/geometry.js` (T06) | `toScreen([x,y], rect) -> [px,py]`, `fromScreen`, `dist`, `angleTo`, `bearing(x, hfovDeg)` |
| `web/common/colours.js` (T02) | `await colourFor(word) -> [r,g,b]` |
| `web/eye/receiver.js` (T26) | `await receivePhoneStream(hub) -> MediaStream` |
| `web/eye/frames.js` (T111) | `startFrameSender(hub, video, {hz, width}) -> {stop(), sent()}`: publishes `camera.frame` |
| `web/eye/restyler.js` (T28) | `createRestyler(config)` → `{start(stream) -> Promise<MediaStream>, setPrompt(text), stop(), onStatus(cb)}` |
| `web/sound/tts.js` (T80) | `createTts()` → `{speak({id, text, voice}) -> Promise<void>, cancel()}` |
| `web/sound/sfx.js` (T81) | `createSfx()` → `{play(name)}` |

## C10. Config keys — `shared/config.json` (T01)

`HUB_PORT, TLS_CERT, TLS_KEY, RADIO_GROUP, RADIO_CHANNEL, DRIVE_HZ, FAILSAFE_MS, SAFETY_STOP_CM, RECOIL_MS,
VISION_HZ, VISION_HOST, VISION_HTTP_PORT, FRAME_WIDTH, CAMERA_HFOV_DEG, VIEW_GRACE_S, OBJECT_FORGET_S,
CLUSTER_GAP, DANGER_SIZE, FRIENDLY_SIZE, NEAR_CM, FACING_HALF_ANGLE_DEG, FACING_MIN_SIZE, AUDIO_DEVICE, AUDIO_RATE,
CLIP_SECONDS, GEMINI_INTERVAL_S, GEMINI_TIMEOUT_S, GEMINI_MODEL, WORLD_CHANGE_THRESHOLD,
RETURN_MATCH_THRESHOLD, NARRATION_MAX_CHARS, TRANSITION_MS, LIGHT_MAX_HZ`.
Secrets (`GEMINI_API_KEY`, video model key) come from environment variables, never from files in the repo.
