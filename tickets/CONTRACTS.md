# Shared contracts — Genrator

Source of truth for behaviour: `genrator-whitepaper.md` (§ numbers in tickets refer to it).
One file = one ticket. Grouping by component: `tickets/Components.md`. Tickets are **not assigned**.

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
web/             Plain JavaScript ES modules, no build step. common/, phone/, eye/, map/, sound/, status/
jetson/          Python 3 overhead vision (OpenCV, a YOLO model, TensorRT where available)
scripts/         Launchers, benches, test tools
tests/           pytest for server/ and jetson/ (mirrors source paths); web tests use `node --test`
docs/            Runbooks and write-ups
```

Firmware can move to MakeCode if the team prefers; the radio packets (C6) stay the same.

## C1. Space and time

- **Table coordinates:** `[x, y]`, floats, normalised so the calibrated table is `0 ≤ x ≤ 1`, `0 ≤ y ≤ 1`.
  Origin is the table's top-left corner as seen from the overhead camera, `y` grows downward.
- **Sizes:** `[w, h]` in the same normalised units. Real size via `config.TABLE_W_CM`, `config.TABLE_H_CM`.
- **Heading:** radians, `0` points along `+x`, increases clockwise (because `y` points down), range `(-π, π]`.
- **Time:** `ts` is Unix seconds as a float, from the sender's clock.
- **IDs:** tracked objects have integer `id`s from the Jetson tracker. Worlds have string `id`s (`"w-" + 8 hex`).
  Giants have string ids `"g<n>"`.

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
| `vision.state` | Jetson (T44), 10 Hz | `{frame_ts, objects:[{id, cls, pos, size, conf}], robot:{pos, heading, seen}\|null, giants:[{id, kind:"hand"\|"person", pos, size, edge:"top"\|"bottom"\|"left"\|"right"}]}` |
| `robot.telemetry` | serial bridge (T22) | `{distance_cm, line:[l, r], override: bool}` |
| `robot.cmd` | light director (T23), threat reaction (T58), reset (T63) | `{kind:"lights", mode:"solid"\|"flash"\|"pulse", rgb:[r,g,b], ms}` or `{kind:"recoil", ms}` or `{kind:"rumble", ms}` |
| `gamepad.button` | serial bridge (T22) | `{button: "light"\|"horn"\|"shout"\|"reset"}` |
| `audio.beat` | beat tracker (T65) | `{tempo_bpm, strength}` (0–1) |
| `audio.features` | features (T66), 20 Hz | `{rms, energy, brightness, silent: bool}` (energy, brightness 0–1) |
| `world.current` | world scheduler (T74) | `{world: World, previous_id: str\|null}` — sent on change and every 5 s |
| `world.transition` | transition coordinator (T95) | `{from: World\|null, to: World, started, duration_ms}` |
| `world.objects` | world objects publisher (T62), 10 Hz | `{world_id, objects:[{id, cls, pos, size, role, name, behaviour, cluster_id, from_sky}], clusters:[{id, pos, member_ids, role, name}], terrain}` |
| `robot.state` | robot state aggregator (T55), 10 Hz | `{pos, heading, seen, distance_cm, override, facing_id: int\|null}` |
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
(T02) maps common colour words to RGB for lights and map tints.

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
| `server/common/geometry.py` (T06) | `dist(a,b)`, `angle_to(a,b)`, `angle_diff(a,b)`, `in_cone(origin, heading, target, half_angle, max_dist)`, `cm_to_units(cm, axis)` |
| `server/common/schemas.py` (T02, T04) | `validate_world(obj) -> list[str]` errors, `validate_envelope(obj) -> list[str]` |
| `server/world/registry.py` (T48) | `ObjectRegistry.update(vision_state, now) -> Diff{added, removed, moved}`; `.get(id)`; `.all()` |
| `server/world/memory.py` (T49) | `RoleMemory.get(world_id, obj_id) -> Role\|None`, `.set(world_id, obj_id, role)`, `.roles_for(world_id)` |
| `server/world/fallback_roles.py` (T51) | `pick_role(world, cls, taken_roles) -> Role` |
| `server/world/clusters.py` (T52) | `find_clusters(objects, max_gap) -> list[Cluster{id, member_ids, pos}]` |
| `server/world/terrain.py` (T53) | `analyse(objects, world) -> {"open_regions": [...], "open_space": str, "under_table": str}` |
| `server/world/worlds.py` (T54) | `WorldRegistry.add(world)`, `.match(signature) -> World\|None`, `.get(id)` |
| `server/audio/capture.py` (T64) | `AudioInput(config).start()`, `.on_block(cb(samples_float32, ts))`, `.last(seconds) -> ndarray`, `.rate` |
| `server/audio/silence.py` (T67) | `SilenceGate().update(rms, ts) -> bool` (true = silent) |
| `server/audio/change.py` (T69) | `ChangeDetector().update(samples, ts) -> bool` (true once per detected song change) |
| `server/world/facing.py` (T56) | `facing(robot_state, objects) -> int\|None` |
| `server/audio/clips.py` (T68) | `ClipStore(audio_input).get_clip(seconds) -> bytes\|None` (16 kHz mono WAV; None if mostly silent) |
| `server/audio/signature.py` (T70) | `signature(window) -> dict`, `distance(sig_a, sig_b) -> float` 0–1 |
| `server/gemini/client.py` (T71) | `async compose_world(audio_wav, image_jpeg, objects, current_world) -> dict` (raw); `async ask_json(parts, schema) -> dict` |
| `server/gemini/prompt.py` (T72) | `build_compose_parts(audio_wav, image_jpeg, objects, current_world, vocab) -> list` |
| `server/gemini/guard.py` (T73) | `guard_world(raw, object_ids, vocab) -> World\|None` |
| `server/gemini/object_role.py` (T76) | `async request_role(world, obj, image_jpeg) -> {role, name, behaviour, announce}\|None` |
| `server/world/fallback_worlds.py` (T75) | `load_fallback_worlds() -> list[World]` |

Every brain module exposes `async def run(hub, config)` if it has its own loop; T104 wires them.

## C8. Jetson interfaces (`jetson/`)

| Module (owner) | Interface |
|---|---|
| `camera.py` (T36) | `Camera(config).read() -> (ts, frame_bgr)`, `.latest() -> (ts, frame_bgr)` |
| `calibration.py` (T37) | `Calibration.load(path)`, `.to_table([u,v]) -> [x,y]`, `.to_pixel([x,y])`, `.contains([u,v])`, `.edge_of([u,v]) -> str\|None` |
| `detector.py` (T38) | `detect(frame) -> list[Detection{bbox:[x1,y1,x2,y2], cls, conf}]` |
| `generic_detector.py` (T110) | `GenericDetector.detect(frame, known: list[Detection]) -> list[Detection]` with `cls="object"` |
| `tracker.py` (T39) | `Tracker.update(dets, ts) -> list[Track{id, cls, bbox, conf}]` |
| `reid.py` (T40) | `ReId.apply(tracks, ts) -> list[Track]` (stable ids across short gaps) |
| `robot_marker.py` (T41) | `find_robot(frame) -> {"px": [u,v], "heading": rad, "bbox": [...]}\|None` (pixel space) |
| `robot_pose.py` (T42) | `RobotPose.update(measurement\|None, ts) -> {pos, heading, seen}` |
| `giants.py` (T43) | `GiantDetector.detect(frame, calib) -> list[{bbox, kind, edge}]` |
| HTTP `GET :<config.JETSON_HTTP_PORT>/snapshot.jpg` (T45) | current overhead frame, people blurred, max 1024 px wide |

## C9. Browser interfaces (`web/`)

| Module (owner) | Interface |
|---|---|
| `web/common/hub.js` (T08) | see C2 |
| `web/common/config.js` (T01) | `await loadConfig() -> object` |
| `web/common/geometry.js` (T06) | `toScreen([x,y], rect) -> [px,py]`, `dist`, `angleTo` |
| `web/common/colours.js` (T02) | `await colourFor(word) -> [r,g,b]` |
| `web/eye/receiver.js` (T26) | `await receivePhoneStream(hub) -> MediaStream` |
| `web/eye/restyler.js` (T28) | `createRestyler(config)` → `{start(stream) -> Promise<MediaStream>, setPrompt(text), stop(), onStatus(cb)}` |
| `web/map/layers/*.js` (T86–T94) | each exports `createLayer()` → `{update(state), draw(ctx, rect, t, beat)}` where `state` holds the latest `world.objects`, `robot.state`, `world.current`, `vision.state` and `audio.*` |
| `web/sound/tts.js` (T80) | `createTts()` → `{speak({id, text, voice}) -> Promise<void>, cancel()}` |
| `web/sound/sfx.js` (T81) | `createSfx()` → `{play(name)}` |

## C10. Config keys — `shared/config.json` (T01)

`HUB_PORT, TLS_CERT, TLS_KEY, RADIO_GROUP, RADIO_CHANNEL, DRIVE_HZ, FAILSAFE_MS, SAFETY_STOP_CM, RECOIL_MS,
TABLE_W_CM, TABLE_H_CM, VISION_HZ, JETSON_HOST, JETSON_HTTP_PORT, OBJECT_GRACE_S, CLUSTER_GAP,
DANGER_RADIUS, FRIENDLY_RADIUS, FACING_HALF_ANGLE_DEG, FACING_MAX_DIST, AUDIO_DEVICE, AUDIO_RATE,
CLIP_SECONDS, GEMINI_INTERVAL_S, GEMINI_TIMEOUT_S, GEMINI_MODEL, WORLD_CHANGE_THRESHOLD,
RETURN_MATCH_THRESHOLD, NARRATION_MAX_CHARS, TRANSITION_MS, LIGHT_MAX_HZ`.
Secrets (`GEMINI_API_KEY`, video model key) come from environment variables, never from files in the repo.
