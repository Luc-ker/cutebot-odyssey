# T111 — First person only: vision on the phone's view, no overhead camera, no map

## What Genrator is (read this first)

**Genrator** (repo `sonar-bot-tune`) is our DurHack 2026 project for the theme *Composition*. A player drives a
palm-sized robot car (an ELECFREAKS Cutebot) around a real table with a handheld gamepad, watching a live feed
from a phone mounted on the robot that an AI video model redraws as a miniature fantasy world. **The music
decides the world:** Gemini listens to a few seconds of whatever is playing, looks at what the robot sees, and
composes a world to match. Every real object the robot discovers gets a role in that world (the chair becomes a
castle) and keeps it, because the vision service recognises each object again when the robot comes back to it.
The robot's lights and the visuals pulse to the beat, hands reaching into the robot's view appear as giants,
threats make the robot recoil, and a narrator announces what happens.

Full detail: `genrator-whitepaper.md`. Shared interfaces every ticket codes to: `tickets/CONTRACTS.md`.

---

## This ticket

> **Goal:** The game is first person only. The phone on the Cutebot is the only camera. Remove the overhead
> camera, the Jetson, the table calibration, the robot marker and the overhead map, and run vision on the
> phone's frames on the laptop.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: core demo | Robot's-eye vision, world logic, ops | §5, §6, §7.3, §7.10, §7.11, §7.13 |

**Assigned to:** _unassigned_

## What changed

- **Frames.** The eye page samples the raw phone stream at `VISION_HZ` and publishes `camera.frame` (JPEG,
  `FRAME_WIDTH` px wide) (`web/eye/frames.js`). The hub delivers this bulk topic only to clients that name it.
- **Vision service.** `jetson/` became `vision/`, run on the laptop as `python -m vision` (started by
  `scripts/launch.py`). Detection (YOLO via `ultralytics`) → tracker (`min_hits=3`) → re-id **by appearance**
  (colour histograms, remembered for `OBJECT_FORGET_S`, so objects keep their id after the robot turns away) →
  `vision.state` in view units. Giants are skin-coloured blobs reaching into the frame from the top or a side,
  plus person detections. `/snapshot.jpg` serves the robot's view, people blurred, on `127.0.0.1` only.
- **Removed:** `calibration.py`, `calibrate_tool.py`, `robot_marker.py`, `robot_pose.py`,
  `generic_detector.py` (background subtraction can't work on a moving camera), the TensorRT bench and export,
  the ArUco marker sheets, `web/map/` and its tickets' code.
- **Registry (T48).** Objects out of view stay known with `visible: false` until `OBJECT_FORGET_S`.
- **Robot state (T55).** `{distance_cm, override, facing_id}`: no position or heading.
- **Facing (T56).** The biggest object near the middle of the view (`FACING_HALF_ANGLE_DEG`, `FACING_MIN_SIZE`,
  `CAMERA_HFOV_DEG`).
- **Proximity (T57).** Near = in view, ahead, and big in the view (`DANGER_SIZE`, `FRIENDLY_SIZE`) or faced
  with the ultrasonic sensor under `NEAR_CM`.
- **Blocked (T60).** A steady short ultrasonic reading, not a still position.
- **Clusters (T52)** group objects in view and carry a `size`; **terrain (T53)** only gives words.
- **Config.** Removed `TABLE_W_CM`, `TABLE_H_CM`, `JETSON_HOST`, `JETSON_HTTP_PORT`, `OBJECT_GRACE_S`,
  `DANGER_RADIUS`, `FRIENDLY_RADIUS`, `FACING_MAX_DIST`; added `VISION_HOST`, `VISION_HTTP_PORT`, `FRAME_WIDTH`,
  `CAMERA_HFOV_DEG`, `VIEW_GRACE_S`, `OBJECT_FORGET_S`, `DANGER_SIZE`, `FRIENDLY_SIZE`, `NEAR_CM`,
  `FACING_MIN_SIZE`.

## Known limits

- Objects the model has no class for (crisp packets, cables) are not detected. Use catalogue objects for the
  demo's threat (a teddy bear, a banana, a cup).
- Two identical-looking objects of the same class can swap ids (and so roles) after the robot turns away.
- With no map, nothing shows where things are on the table; the HUD names what is ahead.

## Acceptance criteria
- [x] `python -m pytest` and `npm test` pass.
- [x] With the hub and `python -m vision` running, `camera.frame` messages produce `vision.state`, and a
  `*` subscriber never receives `camera.frame`.
- [ ] On the real robot: an object the robot turns away from and back to keeps its role; a hand reaching down
  in front of the phone triggers the giant effect; driving up to a threat makes the robot recoil.
