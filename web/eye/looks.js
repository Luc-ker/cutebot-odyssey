// World looks for the local renderer (docs/local-renderer.md): one colour grade and one particle
// effect per world, so the real table reads as part of that world without any generated video.
//
// A look: {tint [r,g,b] 0..255, tintAmount, saturation, contrast, brightness, shadows [r,g,b] -1..1,
// highlights [r,g,b] -1..1, vignette, grain, particles: {kind, count, colour}}.
// `lookForWorld(world)` picks by the world's setting and name (ids like "w-00000004" carry no meaning);
// `lookForPrompt(text)` is the fallback when only a restyle prompt is known. Both are pure.

import { tintForPrompt } from "./restyler.js";

const BASE = {
  tint: [128, 128, 128], tintAmount: 0, saturation: 1.05, contrast: 1.05, brightness: 1,
  shadows: [0, 0, 0], highlights: [0, 0, 0], vignette: 0.3, grain: 0.04,
  particles: { kind: "none", count: 0, colour: [255, 255, 255] },
};

export const LOOKS = {
  kingdom: {
    tint: [255, 205, 130], tintAmount: 0.16, saturation: 1.18, contrast: 1.08, brightness: 1.04,
    shadows: [-0.25, -0.05, 0.35], highlights: [0.45, 0.3, -0.15], vignette: 0.38, grain: 0.045,
    particles: { kind: "motes", count: 46, colour: [255, 226, 150] },
  },
  ocean: {
    tint: [70, 165, 215], tintAmount: 0.3, saturation: 1.12, contrast: 1.06, brightness: 0.98,
    shadows: [-0.3, 0.1, 0.4], highlights: [0.1, 0.3, 0.35], vignette: 0.42, grain: 0.04,
    particles: { kind: "bubbles", count: 34, colour: [210, 240, 255] },
  },
  wasteland: {
    tint: [230, 95, 40], tintAmount: 0.3, saturation: 1.1, contrast: 1.16, brightness: 0.9,
    shadows: [0.1, -0.15, -0.2], highlights: [0.5, 0.2, -0.3], vignette: 0.5, grain: 0.06,
    particles: { kind: "embers", count: 60, colour: [255, 150, 60] },
  },
  snow: {
    tint: [195, 218, 255], tintAmount: 0.26, saturation: 0.85, contrast: 1.04, brightness: 1.08,
    shadows: [-0.1, 0.05, 0.35], highlights: [0.15, 0.2, 0.3], vignette: 0.32, grain: 0.035,
    particles: { kind: "snow", count: 90, colour: [255, 255, 255] },
  },
  neon: {
    tint: [200, 60, 220], tintAmount: 0.24, saturation: 1.3, contrast: 1.2, brightness: 0.92,
    shadows: [0.1, -0.1, 0.45], highlights: [0.4, 0.05, 0.4], vignette: 0.5, grain: 0.05,
    particles: { kind: "motes", count: 30, colour: [120, 240, 255] },
  },
  jungle: {
    tint: [80, 175, 85], tintAmount: 0.22, saturation: 1.2, contrast: 1.08, brightness: 0.98,
    shadows: [-0.2, 0.15, 0.05], highlights: [0.3, 0.35, -0.1], vignette: 0.42, grain: 0.045,
    particles: { kind: "fireflies", count: 28, colour: [210, 255, 120] },
  },
  royal: {
    tint: [240, 190, 95], tintAmount: 0.2, saturation: 1.12, contrast: 1.08, brightness: 1.02,
    shadows: [-0.1, -0.1, 0.3], highlights: [0.45, 0.32, -0.05], vignette: 0.4, grain: 0.04,
    particles: { kind: "motes", count: 40, colour: [255, 215, 120] },
  },
  space: {
    tint: [120, 140, 255], tintAmount: 0.2, saturation: 1.05, contrast: 1.15, brightness: 0.9,
    shadows: [-0.1, -0.05, 0.4], highlights: [0.2, 0.25, 0.4], vignette: 0.55, grain: 0.05,
    particles: { kind: "motes", count: 50, colour: [220, 230, 255] },
  },
};

const MATCH = [
  [["ocean", "sea", "harbour", "reef", "coast", "island"], "ocean"],
  [["wasteland", "volcan", "lava", "ash", "inferno", "desert"], "wasteland"],
  [["snow", "ice", "frost", "winter", "glacier", "tundra"], "snow"],
  [["neon", "cyber", "city", "synth"], "neon"],
  [["jungle", "rainforest", "forest", "swamp", "grove"], "jungle"],
  [["space", "station", "orbit", "galaxy"], "space"],
  [["royal", "court", "palace"], "royal"],
  [["kingdom", "medieval", "castle", "meadow"], "kingdom"],
];
const DARK = ["night", "dusk", "midnight", "dark", "moon"];

function withDark(look, text) {
  return DARK.some((w) => text.includes(w))
    ? { ...look, brightness: look.brightness * 0.78, vignette: Math.min(0.75, look.vignette + 0.15) }
    : look;
}

/** Pure: the look key for some text, or null. */
export function lookKey(text = "") {
  const t = String(text).toLowerCase();
  for (const [words, key] of MATCH) if (words.some((w) => t.includes(w))) return key;
  return null;
}

/** Pure: world (C4 `world.current.world`) -> look. Defaults to Kingdom. */
export function lookForWorld(world) {
  const info = world?.world ?? {};
  const text = `${info.setting ?? ""} ${info.name ?? ""} ${info.time_of_day ?? ""}`.toLowerCase();
  const key = lookKey(`${info.setting ?? ""} ${info.name ?? ""}`) ?? lookKey(world?.restyle_prompt) ?? "kingdom";
  return withDark({ ...BASE, ...LOOKS[key] }, text);
}

/** Pure: restyle prompt -> look; unknown prompts get a mild tint from tintForPrompt. */
export function lookForPrompt(text = "") {
  const t = String(text).toLowerCase();
  const key = lookKey(t);
  if (key) return withDark({ ...BASE, ...LOOKS[key] }, t);
  const { rgb, strength, dark } = tintForPrompt(t);
  const look = { ...BASE, tint: rgb, tintAmount: strength * 0.5 };
  return dark ? withDark(look, "night") : look;
}
