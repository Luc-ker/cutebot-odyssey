// The 3D layer of the local renderer (docs/local-renderer.md): one three.js scene, one model per object.
//
//   const stage = createStage3d(THREE, doc);
//   stage.setModels(worldModelsData)            // `world.models`: Gemini's recipes by object id
//   stage.render(items, W, H, tSeconds, light)  // -> stage.canvas (transparent), to draw over the camera
//
// The camera is orthographic in pixels, so a model is placed exactly where its object is on screen: its
// footprint centred on the object's box, standing on the box's bottom edge, scaled to cover it. Each
// model turns with its position across the view (an object on the left shows its right side), which is
// what makes it read as 3D when the robot turns. Until Gemini's recipe for an object arrives, a seeded
// procedural recipe stands in; when the designed one arrives the model is rebuilt and grows in again.

import { artFor } from "../sprites.js";
import { buildModel } from "./builder.js";
import { normaliseRecipe, proceduralRecipe } from "./recipe.js";

export const COVER = 1.15;      // models are drawn this much larger than the object's box
export const TILT = 0.2;        // radians: we look slightly down on the miniatures
export const TURN = 1.1;        // radians of yaw across the full width of the view
export const KEEP_MS = 3000;    // a model unused this long is disposed

const easeOutBack = (k) => 1 + 2.2 * (k - 1) ** 3 + 1.2 * (k - 1) ** 2;

export const MAX_WIDEN = 1.6;   // a model may be at most this much wider than its object

/**
 * Pure: scale (px per unit) so a model of {w, h, d} covers a box of bw x bh pixels, without letting a
 * short wide model (a village over a bottle) balloon sideways to reach the top of a tall box.
 */
export function fitScale(size, bw, bh, cover = COVER) {
  const width = Math.max(size.w, size.d * 0.7);
  const cover_ = Math.max((bw * cover) / width, (bh * cover) / size.h);
  return Math.min(cover_, (bw * MAX_WIDEN) / width);
}

/** Pure: yaw for an object centred at `cx` (0..1 across the view), plus its own resting angle. */
export function yawFor(cx, seed) {
  return (cx - 0.5) * -TURN + (seed - 0.5) * 0.6;
}

export function createStage3d(THREE, doc = globalThis.document, opts = {}) {
  const canvas = doc.createElement("canvas");
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;

  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(0, 640, 360, 0, -20000, 20000);
  camera.position.set(0, 0, 10000);
  const hemi = new THREE.HemisphereLight(0xfff2dc, 0x5a4630, 1.1);
  const sun = new THREE.DirectionalLight(0xfff0d0, 2.4);
  sun.position.set(-0.6, 1, 0.9);
  const rim = new THREE.DirectionalLight(0x9fc4ff, 0.7);
  rim.position.set(0.7, 0.4, -1);
  scene.add(hemi, sun, rim);

  const designed = new Map(); // object id -> {recipe, key}
  const live = new Map();     // object id -> {model, key, born, lastUsed}
  let W = 0, H = 0;

  function recipeFor(item) {
    const d = designed.get(item.id);
    if (d && d.role === item.role) return d;
    const art = artFor(item.role, item.behaviour);
    const aspect = (item.box.x2 - item.box.x1) * (W / Math.max(H, 1)) / Math.max(item.box.y2 - item.box.y1, 1e-3);
    // Aspect is fixed once per object+role so the model doesn't change shape as the box wobbles.
    const key = `proc|${item.id}|${item.role}`;
    const prev = live.get(item.id);
    if (prev?.key === key) return { key, recipe: prev.model.recipe };
    return { key, recipe: proceduralRecipe(art.key, item.seed, aspect) };
  }

  return {
    canvas,
    kind: "3d",
    /** `world.models` data. */
    setModels(data) {
      for (const m of Array.isArray(data?.models) ? data.models : []) {
        if (!Number.isInteger(m?.id)) continue;
        const recipe = normaliseRecipe(m.recipe);
        if (!recipe) continue;
        const key = `gemini|${m.id}|${m.role}|${recipe.name}|${recipe.parts.length}`;
        if (designed.get(m.id)?.key !== key) designed.set(m.id, { key, recipe, role: m.role });
      }
    },
    reset() {
      designed.clear();
      for (const e of live.values()) e.model.dispose();
      live.clear();
    },
    /** Live model count and how many came from Gemini, for the debug overlay. */
    stats() {
      let gemini = 0;
      for (const e of live.values()) if (e.key.startsWith("gemini|")) gemini++;
      return { models: live.size, gemini };
    },
    /**
     * @param items  scene.items() entries that are sprites (not decals)
     * @param light  {colour: [r,g,b] 0..255 average of the frame, lum: 0..1}
     */
    render(items, width, height, t, light = { colour: [200, 190, 170], lum: 0.5 }) {
      if (width !== W || height !== H) {
        W = width; H = height;
        renderer.setSize(W, H, false);
        camera.left = 0; camera.right = W; camera.top = H; camera.bottom = 0;
        camera.updateProjectionMatrix();
      }
      const nowMs = t * 1000;
      const [r, g, b] = light.colour;
      hemi.color.setRGB(0.55 + r / 510, 0.55 + g / 510, 0.55 + b / 510);
      hemi.intensity = 0.7 + light.lum * 0.9;
      sun.intensity = 1.4 + light.lum * 1.6;

      for (const item of items) {
        const want = recipeFor(item);
        let entry = live.get(item.id);
        if (!entry || entry.key !== want.key) {
          const wasShown = Boolean(entry);
          entry?.model.dispose();
          const model = buildModel(THREE, want.recipe, item.seed);
          scene.add(model.group);
          entry = { model, key: want.key, born: nowMs, swapped: wasShown };
          live.set(item.id, entry);
        }
        entry.lastUsed = nowMs;
        const { model } = entry;
        const bw = (item.box.x2 - item.box.x1) * W, bh = (item.box.y2 - item.box.y1) * H;
        const cx = ((item.box.x1 + item.box.x2) / 2) * W;
        const base = item.box.y2 * H + bh * 0.04;
        // Grow in on first appearance (scene appear) and again when Gemini's design replaces the stand-in.
        const grow = Math.min(item.appear, entry.swapped ? Math.min(1, (nowMs - entry.born) / 500) : 1);
        const s = fitScale(model.size, bw, bh) * Math.max(0.001, easeOutBack(Math.min(1, grow)));
        model.group.scale.setScalar(s);
        model.group.position.set(cx, H - base, item.box.y2 * 4000);
        model.group.rotation.set(TILT, yawFor((item.box.x1 + item.box.x2) / 2, item.seed), 0);
        model.group.visible = item.alpha > 0.01;
        model.setOpacity(item.alpha);
        model.update(t);
      }
      for (const [id, e] of live) {
        if (nowMs - e.lastUsed > 50) e.model.group.visible = false;
        if (nowMs - e.lastUsed > KEEP_MS) { e.model.dispose(); live.delete(id); }
      }
      renderer.render(scene, camera);
      return canvas;
    },
    dispose() {
      this.reset();
      renderer.dispose();
    },
  };
}
