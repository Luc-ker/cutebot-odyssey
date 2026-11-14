# Components → tickets

Which tickets belong to which component of **Genrator** (`genrator-whitepaper.md`).
Shared contracts every ticket codes to: `tickets/CONTRACTS.md`. Tickets are **not assigned**.

Totals: **111 tickets**: 87 P0 (core demo), 22 P1 (polish), 2 P2 (stretch).

> **T111 (first person only)** removed the overhead camera, the Jetson and the map. Tickets marked
> ~~struck through~~ below describe code that no longer exists; tickets marked *(changed by T111)* still
> exist but work in the robot's view now. `tickets/CONTRACTS.md` is up to date and wins over older tickets.

Every ticket can be started on its own. None has to wait for another, because each one codes to the
shared contracts and stubs what it needs.

| # | Component | What it is | Tickets | P0 | P1 | P2 |
|---|---|---|---|---|---|---|
| 1 | [Foundation](#1-foundation) | Config, shared data files, message schemas, the hub and its clients, logging | T01–T10 | 9 | 1 | 0 |
| 2 | [Robot firmware](#2-robot-firmware) | MicroPython on the Cutebot's micro:bit: motors, radio, safety stops, lights, recoil, telemetry | T11–T17 | 6 | 1 | 0 |
| 3 | [Gamepad firmware](#3-gamepad-firmware) | MicroPython on the gamepad's micro:bit: joystick driving, buttons, rumble | T18–T20 | 2 | 0 | 1 |
| 4 | [Bridge](#4-bridge) | The USB micro:bit and the laptop service that link radio to the hub, plus the light director | T21–T24 | 3 | 1 | 0 |
| 5 | [Robot's-eye view](#5-robots-eye-view) | Phone camera stream, AI restyling, the main screen and its overlays | T25–T35 | 8 | 3 | 0 |
| 6 | [Robot's-eye vision](#6-robots-eye-vision) | Vision on the phone's frames, on the laptop: detection, tracking, re-id, giants, snapshots | T36–T47, T110, T111 | 12 | 2 | 0 |
| 7 | [World memory & game logic](#7-world-memory--game-logic) | Object registry, per-world roles, arrivals, clusters, terrain, proximity and reactions | T48–T63 | 12 | 4 | 0 |
| 8 | [Audio pipeline](#8-audio-pipeline) | Microphone capture, beat, energy, silence, clips for Gemini, change detection, signatures | T64–T70 | 6 | 1 | 0 |
| 9 | [Gemini world composer](#9-gemini-world-composer) | The Gemini call, its prompt and guard, the world loop, fallback worlds, eval | T71–T78 | 5 | 2 | 1 |
| 10 | [Narration & sound](#10-narration--sound) | Narration queue, text-to-speech, sound effects, what gets said and when, button actions | T79–T84 | 6 | 0 | 0 |
| 11 | [~~Overhead map~~](#11-overhead-map-removed) | Removed by T111: first person only | ~~T85–T94~~ | 6 | 4 | 0 |
| 12 | [World transitions](#12-world-transitions) | The single timed event that makes a world change one deliberate moment | T95 | 1 | 0 | 0 |
| 13 | [Integration & ops](#13-integration--ops) | Launcher, status page, wiring, runbooks, physical build, privacy, latency, write-up | T96–T105 | 7 | 3 | 0 |
| 14 | [Acceptance tests](#14-acceptance-tests) | End-to-end checks of the whitepaper's promises, run with fakes | T106–T109 | 4 | 0 | 0 |

---

## 1. Foundation

Config, shared data files, message schemas, the hub and its clients, logging.

| Ticket | Title | Priority |
|---|---|---|
| [T01](T01-config-file.md) | Shared config file with Python and JS loaders | P0 |
| [T02](T02-world-schema.md) | World JSON Schema, validator and colour words | P0 |
| [T03](T03-roles-vocabulary.md) | Roles vocabulary data file | P0 |
| [T04](T04-hub-envelope-schemas.md) | Hub envelope and topic payload validators | P0 |
| [T05](T05-radio-codec.md) | Radio packet codec (laptop side and micro:bit side) | P0 |
| [T06](T06-geometry-helpers.md) | Geometry helpers (Python and JS) *(changed by T111: view units)* | P0 |
| [T07](T07-hub-server.md) | Hub server (WebSocket pub/sub plus static files) | P0 |
| [T08](T08-hub-client-js.md) | Hub client for browser pages | P0 |
| [T09](T09-hub-client-py.md) | Hub client for Python services | P0 |
| [T10](T10-trace-logging.md) | Structured logging and latency tracing | P1 |

## 2. Robot firmware

MicroPython on the Cutebot's micro:bit: motors, radio, safety stops, lights, recoil, telemetry.

| Ticket | Title | Priority |
|---|---|---|
| [T11](T11-cutebot-motors.md) | Cutebot motor driver | P0 |
| [T12](T12-cutebot-radio-failsafe.md) | Cutebot radio receiver and failsafe stop | P0 |
| [T13](T13-ultrasonic-safety-stop.md) | Ultrasonic safety stop | P0 |
| [T14](T14-edge-stop.md) | Line-sensor table edge stop | P1 |
| [T15](T15-cutebot-lights.md) | Cutebot light effects engine | P0 |
| [T16](T16-recoil.md) | Automatic recoil manoeuvre | P0 |
| [T17](T17-cutebot-telemetry.md) | Cutebot telemetry broadcast | P0 |

## 3. Gamepad firmware

MicroPython on the gamepad's micro:bit: joystick driving, buttons, rumble.

| Ticket | Title | Priority |
|---|---|---|
| [T18](T18-gamepad-drive.md) | Gamepad joystick drive sender | P0 |
| [T19](T19-gamepad-buttons.md) | Gamepad buttons to actions | P0 |
| [T20](T20-gamepad-rumble.md) | Gamepad rumble on threat | P2 |

## 4. Bridge

The USB micro:bit and the laptop service that link radio to the hub, plus the light director.

| Ticket | Title | Priority |
|---|---|---|
| [T21](T21-bridge-firmware.md) | Bridge micro:bit firmware (serial ↔ radio) | P0 |
| [T22](T22-serial-bridge-service.md) | Laptop serial bridge service | P0 |
| [T23](T23-light-director.md) | Robot light director | P0 |
| [T24](T24-radio-contention-bench.md) | Radio contention test bench | P1 |

## 5. Robot's-eye view

Phone camera stream, AI restyling, the main screen and its overlays.

| Ticket | Title | Priority |
|---|---|---|
| [T25](T25-phone-camera-page.md) | Phone camera streaming page | P0 |
| [T26](T26-webrtc-receiver.md) | Laptop WebRTC receiver for the phone stream | P0 |
| [T27](T27-restyle-provider-spike.md) | Pick the real-time video restyle model | P0 |
| [T28](T28-restyler-adapter.md) | Restyler adapter | P0 |
| [T29](T29-prompt-composer.md) | Restyle prompt composer | P0 |
| [T30](T30-prompt-blending.md) | Prompt blending during world changes | P1 |
| [T31](T31-eye-display-page.md) | Robot's-eye display page | P0 |
| [T32](T32-eye-hud.md) | Robot's-eye HUD overlay | P0 |
| [T33](T33-raw-fallback.md) | Raw-feed fallback mode | P0 |
| [T34](T34-eye-beat-pulse.md) | Beat pulse on the robot's-eye view | P1 |
| [T35](T35-eye-giant-effect.md) | Giant arrival effect on the robot's-eye view | P1 |

## 6. Robot's-eye vision

The vision service (`python -m vision`) on the laptop, fed by the phone's frames: detection, tracking, re-id,
giants, snapshots.

| Ticket | Title | Priority |
|---|---|---|
| [T36](T36-overhead-camera.md) | Local camera capture *(changed by T111: development source only)* | P0 |
| ~~[T37](T37-table-calibration.md)~~ | ~~Table calibration and boundary~~ (removed by T111) | P0 |
| [T38](T38-object-detector.md) | Object detector | P0 |
| [T39](T39-object-tracker.md) | Persistent-ID object tracker | P0 |
| [T40](T40-short-reid.md) | Re-identification *(changed by T111: by appearance, long memory)* | P0 |
| ~~[T41](T41-robot-marker.md)~~ | ~~Robot marker detection~~ (removed by T111) | P0 |
| ~~[T42](T42-robot-pose-filter.md)~~ | ~~Robot pose smoothing and freeze on loss~~ (removed by T111) | P0 |
| [T43](T43-giant-detection.md) | Hand and person (giant) detection *(changed by T111: hands reaching into the view)* | P0 |
| [T44](T44-vision-publisher.md) | Vision state publisher *(changed by T111: `python -m vision` on the laptop)* | P0 |
| [T45](T45-snapshot-endpoint.md) | Robot's-view snapshot endpoint with people blurred *(changed by T111)* | P0 |
| ~~[T46](T46-tensorrt-bench.md)~~ | ~~TensorRT export and FPS benchmark~~ (removed by T111) | P1 |
| [T47](T47-vision-replay.md) | Vision replay and synthetic robot's-view scenes *(changed by T111)* | P0 |
| ~~[T110](T110-generic-object-detector.md)~~ | ~~Generic detector for non-catalogue objects~~ (removed by T111: needs a still camera) | P1 |
| [T111](T111-first-person-vision.md) | First person only: vision on the phone's view, no overhead camera, no map | P0 |

## 7. World memory & game logic

Object registry, per-world roles, arrivals, clusters, terrain, proximity and reactions.

| Ticket | Title | Priority |
|---|---|---|
| [T48](T48-object-registry.md) | Object registry *(changed by T111: out of view ≠ removed)* | P0 |
| [T49](T49-role-memory.md) | Per-world role memory | P0 |
| [T50](T50-object-arrivals.md) | New and removed object flow | P0 |
| [T51](T51-fallback-role-picker.md) | Local fallback role picker | P0 |
| [T52](T52-clustering.md) | Object clustering into places *(changed by T111: objects in view)* | P1 |
| [T53](T53-terrain-analysis.md) | Terrain words *(changed by T111: no open regions)* | P1 |
| [T54](T54-world-registry.md) | World registry and returning-song match | P0 |
| [T55](T55-robot-state.md) | Robot state aggregator *(changed by T111: no pose)* | P0 |
| [T56](T56-facing-object.md) | Facing-object detection *(changed by T111: middle of the view)* | P0 |
| [T57](T57-proximity-zones.md) | Danger and friendly proximity events *(changed by T111: size in view + ultrasonic)* | P0 |
| [T58](T58-threat-reaction.md) | Threat reaction (recoil, warning, rumble) | P0 |
| [T59](T59-friendly-reaction.md) | Friendly approach reaction | P1 |
| [T60](T60-blocked-reaction.md) | Physical-block detection *(changed by T111: steady ultrasonic reading)* | P1 |
| [T61](T61-giant-events.md) | Giant enter and leave events | P0 |
| [T62](T62-world-objects-publisher.md) | World objects publisher | P0 |
| [T63](T63-reset.md) | Gamepad reset and full demo reset | P0 |

## 8. Audio pipeline

Microphone capture, beat, energy, silence, clips for Gemini, change detection, signatures.

| Ticket | Title | Priority |
|---|---|---|
| [T64](T64-audio-capture.md) | Audio input capture | P0 |
| [T65](T65-beat-tracker.md) | Beat and tempo tracker | P0 |
| [T66](T66-audio-features.md) | Energy and brightness features | P0 |
| [T67](T67-silence-gate.md) | Silence detection | P0 |
| [T68](T68-clip-store.md) | Audio clip store for Gemini | P0 |
| [T69](T69-music-change.md) | Local music-change detector | P1 |
| [T70](T70-music-signature.md) | Music signature | P0 |

## 9. Gemini world composer

The Gemini call, its prompt and guard, the world loop, fallback worlds, eval.

| Ticket | Title | Priority |
|---|---|---|
| [T71](T71-gemini-client.md) | Gemini client wrapper | P0 |
| [T72](T72-composer-prompt.md) | World composer prompt | P0 |
| [T73](T73-response-guard.md) | Gemini response guard | P0 |
| [T74](T74-world-scheduler.md) | World scheduler and change decision | P0 |
| [T75](T75-fallback-worlds.md) | Pre-composed fallback worlds | P0 |
| [T76](T76-object-role-call.md) | Single-object role call | P1 |
| [T77](T77-talking-objects.md) | Talking objects | P2 |
| [T78](T78-gemini-eval.md) | Gemini evaluation harness | P1 |

## 10. Narration & sound

Narration queue, text-to-speech, sound effects, what gets said and when, button actions.

| Ticket | Title | Priority |
|---|---|---|
| [T79](T79-narration-queue.md) | Narration queue | P0 |
| [T80](T80-tts.md) | Text-to-speech in the browser | P0 |
| [T81](T81-sound-page.md) | Sound effects and the sound page | P0 |
| [T82](T82-narration-triggers.md) | Narration triggers | P0 |
| [T83](T83-shout-button.md) | Shout: describe what is ahead | P0 |
| [T84](T84-horn-light-buttons.md) | Horn and Light buttons | P0 |

## 11. Overhead map (removed)

Removed by T111: the game is first person only, and nothing knows where things are on the table.

| Ticket | Title | Priority |
|---|---|---|
| ~~[T85](T85-map-shell.md)~~ | ~~Overhead map page shell and renderer~~ | P0 |
| ~~[T86](T86-map-terrain.md)~~ | ~~Map terrain layer~~ | P0 |
| ~~[T87](T87-map-objects.md)~~ | ~~Map object icon layer~~ | P0 |
| ~~[T88](T88-role-icons.md)~~ | ~~Role icon art set~~ | P0 |
| ~~[T89](T89-map-robot.md)~~ | ~~Map robot marker and trail~~ | P0 |
| ~~[T90](T90-map-danger.md)~~ | ~~Map danger glow layer~~ | P1 |
| ~~[T91](T91-map-giants.md)~~ | ~~Map giant shadow layer~~ | P1 |
| ~~[T92](T92-map-info.md)~~ | ~~Map info corner~~ | P0 |
| ~~[T93](T93-map-beat.md)~~ | ~~Beat envelope for the map~~ | P1 |
| ~~[T94](T94-map-transition.md)~~ | ~~Map world-transition morph~~ | P1 |

## 12. World transitions

The single timed event that makes a world change one deliberate moment.

| Ticket | Title | Priority |
|---|---|---|
| [T95](T95-transition-coordinator.md) | World transition coordinator | P0 |

## 13. Integration & ops

Launcher, status page, wiring, runbooks, physical build, privacy, latency, write-up.

| Ticket | Title | Priority |
|---|---|---|
| [T96](T96-launcher.md) | One-command launcher | P0 |
| [T97](T97-status-page.md) | Status and control page | P0 |
| [T98](T98-latency-harness.md) | Latency measurement against targets | P1 |
| [T99](T99-privacy-check.md) | Privacy guarantees check | P0 |
| [T100](T100-network-runbook.md) | Network runbook | P0 |
| [T101](T101-physical-build.md) | Physical build: phone mount, edge tape *(changed by T111: no marker, no camera rig)* | P0 |
| [T102](T102-demo-audio.md) | Demo audio setup and playlist | P0 |
| [T103](T103-backup-video.md) | Backup demo recording | P1 |
| [T104](T104-brain-entrypoint.md) | Game brain entrypoint (wiring) | P0 |
| [T105](T105-devpost-writeup.md) | Devpost write-up, README and AI disclosure | P1 |

## 14. Acceptance tests

End-to-end checks of the whitepaper's promises, run with fakes.

| Ticket | Title | Priority |
|---|---|---|
| [T106](T106-at-role-persistence.md) | Acceptance test: roles persist | P0 |
| [T107](T107-at-song-change.md) | Acceptance test: song change changes the world | P0 |
| [T108](T108-at-giant-threat.md) | Acceptance test: giant and threat recoil | P0 |
| [T109](T109-at-degradation.md) | Acceptance test: graceful degradation | P0 |
