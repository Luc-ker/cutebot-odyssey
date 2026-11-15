# Local renderer

The robot's-eye screen turns real objects into the world's miniatures (a bottle becomes a watchtower,
a cup a beacon) by drawing graphics over them on the laptop, at the camera's frame rate. There is no AI
video model in the loop, so it needs no account, no credits and no network, and every object becomes
exactly the miniature its role says, in exactly the right place, on every frame.

It is the default restyle provider (`GENRATOR_RESTYLE_PROVIDER=local`). `fake` (tint only) and `decart`
remain available; see [restyle-provider.md](restyle-provider.md).

## How it works

```
phone camera ──WebRTC──► eye page ──camera.frame {jpeg, t}──► vision (YOLO11n-seg)
                            ▲                                      │
                            └──── vision.state {objects: pos, size, outline; client_ts} ◄┘
                                   world.objects {id → role}  (brain, or the Kingdom class table)

eye page, every video frame (web/eye/compositor.js):
  camera frame
  → for each object with a role, farthest first:
       cover   outline enlarged and filled with the surrounding colour (soft-edged, low-res layer)
       shadow  soft contact shadow under it
       sprite  the role's miniature, covering the box, standing on its bottom edge,
               shaded towards the colour and brightness around it
       decal   flat roles (river, road, bridge, glacier, ash field) fill the outline with a texture
  → world particles (motes, embers, snow, bubbles, fireflies)
  → colour grade + vignette + film grain over everything (WebGL, web/eye/grade.js)
```

| File | What |
|---|---|
| `vision/detector.py` | Segmentation model; each detection carries `extra["outline"]` (24 points) |
| `vision/state.py` | `vision.state.objects[].outline` in view units; `client_ts` echoes `camera.frame.t` |
| `web/eye/scene.js` | Per-object prediction to the current video frame, One Euro smoothing, fade in/out |
| `web/eye/sprites.js` | Role → sprite or decal; Kingdom class → role table for when the brain is off |
| `web/eye/sprites/*.svg` | 16 hand-drawn miniatures, rasterised once at load |
| `web/eye/looks.js` | One grade and particle effect per world |
| `web/eye/compositor.js` | The drawing |
| `web/eye/grade.js` | The WebGL grade pass (Canvas 2D fallback) |

### Keeping graphics on the objects

Vision arrives ten times a second, roughly 100–250 ms after the frame it describes. The eye page stamps
each frame it sends with its own clock (`camera.frame.t`) and vision returns that stamp as
`vision.state.client_ts`, so the page knows exactly how old each state is. Each object's box is
extrapolated at its measured velocity to the current frame (never more than 300 ms ahead) and smoothed
with a One Euro filter, which stays still when the object is still and keeps up when the robot turns.
Outlines are stored relative to their box, so they move with it. An object that vision stops reporting
is held for 350 ms, then fades out over 250 ms. A newly assigned role grows in over 450 ms.

### Why it looks like part of the scene

- **Cover, don't erase.** Sprites are drawn 12% larger than the object's box, and the object's outline
  (enlarged 22%) is first painted in the colour around it, so nothing peeks through.
- **Contact shadow** under every sprite.
- **Light matching:** a 32×18 copy of the frame (refreshed five times a second) gives the colour and
  brightness around each object; the sprite is tinted towards it and darkened in shadow.
- **One grade for everything:** camera and sprites go through the same colour grade and grain.
- **Miniature art style:** painted toy-like miniatures hide small edge and lighting errors that
  photoreal sprites would expose.

## Running it

Nothing extra to start: `python scripts/launch.py` and open the eye page as before. The renderer label
(top right) says "Local renderer". Keys on the eye page: **D** toggles outlines, boxes, roles and the
measured vision age; **R** shows the raw camera.

Without a segmentation model (for example `--model vision/models/yolo11n.pt`) objects are covered by an
ellipse inside their box instead of their outline.

### Make vision fast on an Intel laptop (OpenVINO)

Segmentation is heavier than detection. On Intel CPUs and Iris Xe graphics, export the model to
OpenVINO once; the vision service picks the export up automatically:

```bash
pip install openvino
```

```bash
yolo export model=vision/models/yolo11n-seg.pt format=openvino
```

This creates `vision/models/yolo11n-seg_openvino_model/`. If vision is still below about 8 fps
(`system.health` shows it), run it at a smaller input size: `python -m vision --imgsz 320`.

### Preview without the robot

`web/eye/preview.html` shows the renderer on a synthetic table that pans like a turning robot, with fake
vision states delayed by 150 ms. Serve the repository and open it:

```bash
python -m http.server 8137 --bind 127.0.0.1
```

Then visit `http://127.0.0.1:8137/web/eye/preview.html`. You can switch the world look, show the
outlines and view the camera side by side. Add `?camera` to use the laptop's webcam (there's no
detection then). Keep the page visible: background tabs are throttled to about 1 fps.

Measured on this laptop (Intel Iris Xe) in the preview: 27–28 fps composited, against a 30 fps
source. Before the blur filters were replaced it ran at 16 fps.

## Decart on top (optional)

`GENRATOR_RESTYLE_PROVIDER=decart` with `GENRATOR_DECART_INPUT=composited` sends the local renderer's
output to Decart instead of the raw camera, so the model only repaints a scene that already has the
right miniatures in the right places. That still uses Decart credits.

## Adding art

Add `web/eye/sprites/<key>.svg` (with `viewBox`, `width` and `height`; the bottom of the drawing is the
ground line), add the key to `SPRITE_KEYS` and map roles to it in `ROLE_ART` in `web/eye/sprites.js`. Light
comes from the upper left. `npm test` checks that every role in `shared/roles.json` has art and every key
has a file.
