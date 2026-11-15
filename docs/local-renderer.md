# Local renderer

The robot's-eye screen turns real objects into the world's miniatures (a bottle becomes a watchtower,
a cup a beacon) by drawing **live 3D models** over them on the laptop, at the camera's frame rate.
**Gemini designs each object's model**: a unique recipe of simple 3D parts that echoes the real
object's shape and colour and suits the world. Until Gemini's design arrives (or with no network) a
seeded procedural model stands in, so every object is different from the first frame. There is no AI
video model in the loop, so the picture never waits on the network, and every object becomes exactly
the miniature its role says, in exactly the right place, on every frame.

It is the default restyle provider (`GENRATOR_RESTYLE_PROVIDER=local`). `fake` (tint only) and `decart`
remain available; see [restyle-provider.md](restyle-provider.md).

## How it works

```
phone camera ──WebRTC──► eye page ──camera.frame {jpeg, t}──► vision (YOLO11n-seg)
                            ▲                                      │
                            └──── vision.state {objects: pos, size, outline; client_ts} ◄┘
                                   world.objects {id → role}  (brain, or the Kingdom class table)

brain: server/gemini/model_designer.py
  world.objects (a new role) + snapshot crop ──► Gemini ──► recipe (shared/schemas/model.schema.json)
  ──► world.models {id → recipe}, once a second; cached in logs/model_cache.json

eye page, every video frame (web/eye/compositor.js):
  camera frame
  → for each object with a role, farthest first:
       cover   outline enlarged and filled with the surrounding colour (soft-edged, low-res layer)
       shadow  soft contact shadow under it
       model   a three.js 3D miniature (web/eye/models/): Gemini's recipe, or a seeded procedural
               one until it arrives; covering the box, standing on its bottom edge, lit by the
               frame's light, turning with its place in the view, animated (flames, flags, wings)
       decal   flat roles (river, road, bridge, glacier, ash field) fill the outline with a texture
       sprite  only if three.js can't load: the role's flat SVG miniature
  → world particles (motes, embers, snow, bubbles, fireflies)
  → colour grade + vignette + film grain over everything (WebGL, web/eye/grade.js)
```

| File | What |
|---|---|
| `vision/detector.py` | Segmentation model; each detection carries `extra["outline"]` (24 points) |
| `vision/state.py` | `vision.state.objects[].outline` in view units; `client_ts` echoes `camera.frame.t` |
| `web/eye/scene.js` | Per-object prediction to the current video frame, One Euro smoothing, fade in/out |
| `server/gemini/model_designer.py` | Asks Gemini for one model recipe per object, checks it, caches it, publishes `world.models` |
| `shared/schemas/model.schema.json` | The recipe format, also Gemini's response schema |
| `web/eye/models/recipe.js` | Recipe checks (same rules as the Python guard) and 16 seeded procedural generators |
| `web/eye/models/builder.js` | Recipe → three.js model with materials and part animations |
| `web/eye/models/stage3d.js` | The 3D scene: places, scales, turns and lights every model |
| `web/eye/sprites.js` | Role → archetype or decal; Kingdom class → role table for when the brain is off |
| `web/eye/sprites/*.svg` | 16 flat miniatures, used only when three.js can't load |
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

### Gemini-designed models

`server/gemini/model_designer.py` runs in the brain's `gemini` group. When `world.objects` gives an
object a role, it sends Gemini the world, the role (and its description from `shared/roles.json`), the
real object's class and on-screen proportions, and a crop of the object from the vision snapshot. Gemini
answers with a recipe: up to 32 parts (box, cylinder, cone, sphere, dome, pyramid, torus, wedge, capsule),
each with a size, position, colour, material (stone, wood, metal, gold, cloth, leaf, scale, crystal,
water, glow), optional rotation, optional ring or line repeats, and optional animation (flicker, flap,
sway, spin, bob, pulse). Every answer is checked and repaired on both sides (`normalise_recipe` in Python,
`normaliseRecipe` in JS), so a bad answer can't break the picture.

- One request at a time, at most `MODEL_DESIGN_PER_MIN` (10) a minute; visible objects first.
- Stable Kingdom mode designs one model per detector class (every bottle is the same tower), otherwise
  one per object.
- Designs are kept in `logs/model_cache.json` per world setting and role. Once `MODEL_VARIANTS_PER_ROLE`
  (3) exist, new objects with that role reuse one of them, so a long demo doesn't keep paying for calls
  and a restart starts with Gemini's models already there.
- `MODEL_DESIGN_ENABLED: false` turns it off; the eye page then uses procedural models only.

When Gemini's model for an object arrives, the stand-in shrinks away and the designed model grows in.
Press **D** on the eye page to see how many models are on screen and how many came from Gemini.

Needs `GEMINI_API_KEY` in the repository's `.env` and the `google-genai` package, as for the world composer.

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

Then visit `http://127.0.0.1:8137/web/eye/preview.html` (add `?gallery` to see one model of every
archetype side by side). You can switch the world look, show the
outlines and view the camera side by side. Add `?camera` to use the laptop's webcam (there's no
detection then). Keep the page visible: background tabs are throttled to about 1 fps.

Measured on this laptop (Intel Iris Xe) in the preview: 29–30 fps composited with live 3D models,
against a 30 fps source. three.js is loaded from jsDelivr (pinned `three@0.170.0`), so the eye page
needs the network once at start; without it the flat sprites are used.

## Decart on top (optional)

`GENRATOR_RESTYLE_PROVIDER=decart` with `GENRATOR_DECART_INPUT=composited` sends the local renderer's
output to Decart instead of the raw camera, so the model only repaints a scene that already has the
right miniatures in the right places. That still uses Decart credits.

## Adding art

New 3D archetypes: add a generator to `GEN` in `web/eye/models/recipe.js` and map roles to it in
`ROLE_ART` in `web/eye/sprites.js`. Check it in `preview.html?gallery`.

Flat fallback sprites:

Add `web/eye/sprites/<key>.svg` (with `viewBox`, `width` and `height`; the bottom of the drawing is the
ground line), add the key to `SPRITE_KEYS` and map roles to it in `ROLE_ART` in `web/eye/sprites.js`. Light
comes from the upper left. `npm test` checks that every role in `shared/roles.json` has art and every key
has a file.
