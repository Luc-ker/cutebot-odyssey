// Sprite art for the local renderer (docs/local-renderer.md).
//
// Every role in shared/roles.json is drawn as one of a small set of hand-made miniatures in
// web/eye/sprites/<key>.svg ("sprite"), or, for flat ground features, as a textured patch filling the
// object's outline ("decal"). `artFor(role, behaviour)` is pure; `loadSprites()` rasterises the SVGs once
// so the frame loop only ever blits bitmaps.

export const SPRITE_KEYS = [
  "castle", "palace", "fortress", "temple", "tower", "beacon", "village", "tree", "dragon", "beast",
  "treasure", "cave", "crystal", "ship", "mountain", "monolith",
];
export const DECAL_KEYS = ["water", "cobble", "planks", "ice", "ash"];

const ROLE_ART = {
  castle: "castle",
  palace: "palace", throne_room: "palace", ice_palace: "palace", observatory: "palace",
  fortress: "fortress", engine_room: "fortress",
  temple: "temple", ruin: "temple",
  tower: "tower", watchtower: "tower", lighthouse: "tower", skyscraper: "tower", docking_tower: "tower",
  beacon: "beacon",
  village: "village", market: "village", harbour: "village", camp: "village", snow_cottage: "village",
  neon_arcade: "village",
  forest: "tree", grove: "tree", jungle_patch: "tree",
  dragon: "dragon", sea_serpent: "dragon", lava_beast: "dragon",
  wolf_pack: "beast", jaguar: "beast", yeti: "beast", robot_sentinel: "beast", drone_swarm: "beast",
  treasure: "treasure", relic: "treasure",
  crystal: "crystal",
  catacombs: "cave", den: "cave", lava_cave: "cave", subway: "cave",
  ship: "ship", raft: "ship", boat: "ship", shipwreck: "ship",
  mountain: "mountain", volcano: "mountain", cliff: "mountain", island: "mountain", asteroid: "mountain",
};
const ROLE_DECAL = { river: "water", road: "cobble", bridge: "planks", glacier: "ice", ash_field: "ash" };
const BY_BEHAVIOUR = { threat: "beast", friendly: "village", neutral: "monolith" };

/** Pure: role -> {kind: "sprite"|"decal", key}. Unknown roles fall back on their behaviour. */
export function artFor(role, behaviour = null) {
  const r = String(role ?? "").toLowerCase();
  if (ROLE_DECAL[r]) return { kind: "decal", key: ROLE_DECAL[r] };
  if (ROLE_ART[r]) return { kind: "sprite", key: ROLE_ART[r] };
  return { kind: "sprite", key: BY_BEHAVIOUR[behaviour] ?? "monolith" };
}

// Stable Kingdom mode gives every detector class one fixed role (server/world/fallback_roles.class_role).
// The same table here lets the eye page keep drawing when the brain is not running.
const KINGDOM_CLASS_ROLES = {
  apple: "grove", backpack: "dragon", banana: "den", book: "throne_room", bottle: "watchtower", bowl: "market",
  broccoli: "forest", cake: "relic", carrot: "grove", "cell phone": "treasure", chair: "throne_room",
  clock: "palace", cup: "beacon", donut: "palace", fork: "temple", frisbee: "fortress", handbag: "market",
  keyboard: "road", knife: "harbour", laptop: "fortress", mouse: "wolf_pack", orange: "grove",
  "potted plant": "forest", remote: "river", sandwich: "harbour", scissors: "dragon", shoe: "den",
  spoon: "road", "sports ball": "dragon", suitcase: "dragon", "teddy bear": "wolf_pack", tie: "catacombs",
  toothbrush: "temple", "toy car": "village", umbrella: "market", vase: "palace", "wine glass": "watchtower",
};
const THREATS = new Set(["dragon", "wolf_pack"]);

/** Pure: the Kingdom role for a detector class when world.objects is not arriving. */
export function kingdomRoleForClass(cls) {
  const role = KINGDOM_CLASS_ROLES[String(cls ?? "").toLowerCase()] ?? "castle";
  return { role, behaviour: THREATS.has(role) ? "threat" : "neutral" };
}

/** Pure: target bitmap size for an SVG of `w`x`h`, `height` px tall. */
export function rasterSize(w, h, height = 384) {
  if (!(w > 0 && h > 0)) return [height, height];
  return [Math.max(1, Math.round((w / h) * height)), height];
}

/**
 * Load and rasterise every sprite. Resolves once all have loaded or failed (a missing one is skipped).
 * @returns {Promise<{get(key: string): HTMLCanvasElement|null, keys: string[]}>}
 */
export async function loadSprites({ base = new URL("./sprites/", import.meta.url).href, height = 384,
  doc = globalThis.document } = {}) {
  const bitmaps = new Map();
  await Promise.all(SPRITE_KEYS.map((key) => new Promise((resolve) => {
    const img = new Image();
    img.decoding = "async";
    img.onload = () => {
      const [w, h] = rasterSize(img.naturalWidth, img.naturalHeight, height);
      const c = doc.createElement("canvas");
      c.width = w; c.height = h;
      const g = c.getContext("2d");
      g.filter = "blur(0.6px)"; // once, here: a crisp vector edge looks pasted on next to camera blur
      g.drawImage(img, 0, 0, w, h);
      bitmaps.set(key, c);
      resolve();
    };
    img.onerror = () => { console.warn(`[sprites] ${key}.svg did not load`); resolve(); };
    img.src = `${base}${key}.svg`;
  })));
  return { get: (key) => bitmaps.get(key) ?? bitmaps.get("monolith") ?? null, keys: [...bitmaps.keys()] };
}
