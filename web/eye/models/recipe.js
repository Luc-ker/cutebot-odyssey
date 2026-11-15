// 3D model recipes (shared/schemas/model.schema.json): checking them, and generating them procedurally.
//
// A recipe is a list of simple parts (box, cylinder, cone, sphere, dome, pyramid, torus, wedge, capsule)
// standing on the ground at y = 0, about 1 unit tall. Gemini designs one per object
// (server/gemini/model_designer.py). Until it arrives, or with no network, `proceduralRecipe` makes one:
// seeded by the object id, so every object gets its own variation of its archetype (towers differ in
// height, roof colour, battlements, banners; dragons in colour, horns, wing span...), shaped to the real
// object's proportions. All pure: no three.js, no DOM.

export const SHAPES = ["box", "cylinder", "cone", "sphere", "dome", "pyramid", "torus", "wedge", "capsule"];
export const MATERIALS = ["stone", "wood", "metal", "gold", "cloth", "leaf", "scale", "crystal", "water", "glow"];
export const PART_ANIMS = ["none", "spin", "bob", "sway", "flicker", "flap", "pulse"];
export const MODEL_ANIMS = ["none", "bob", "spin", "sway", "breathe"];
export const MAX_PARTS = 32;
export const MAX_EXPANDED = 120;

const clamp = (v, lo, hi, d) => {
  const n = Number(v);
  return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : d;
};
const vec = (v, lo, hi, d) => (Array.isArray(v) && v.length === 3 ? v.map((x, i) => clamp(x, lo, hi, d[i])) : [...d]);

/** Pure: a safe recipe (same rules as the Python guard), or null. */
export function normaliseRecipe(raw) {
  if (!raw || typeof raw !== "object" || !Array.isArray(raw.parts)) return null;
  const parts = [];
  let expanded = 0;
  for (const p of raw.parts.slice(0, MAX_PARTS)) {
    if (!p || !SHAPES.includes(p.shape) || !/^#[0-9a-f]{6}$/i.test(p.colour ?? "")) continue;
    const pos = vec(p.pos, -10, 10, [0, 0, 0]);
    const part = {
      shape: p.shape,
      size: vec(p.size, 0.02, 1.2, [0.2, 0.2, 0.2]),
      pos: [clamp(pos[0], -0.8, 0.8, 0), clamp(pos[1], 0, 1.4, 0), clamp(pos[2], -0.8, 0.8, 0)],
      colour: p.colour.toLowerCase(),
      material: MATERIALS.includes(p.material) ? p.material : "stone",
    };
    if (p.rot) part.rot = vec(p.rot, -180, 180, [0, 0, 0]);
    if (PART_ANIMS.includes(p.anim) && p.anim !== "none") part.anim = p.anim;
    let copies = 1;
    if (p.repeat && (p.repeat.mode === "ring" || p.repeat.mode === "line")) {
      const count = Math.round(clamp(p.repeat.count, 2, 12, 2));
      part.repeat = p.repeat.mode === "ring"
        ? { count, mode: "ring", radius: clamp(p.repeat.radius, 0.02, 0.8, 0.3) }
        : { count, mode: "line", spacing: clamp(p.repeat.spacing, 0.02, 0.6, 0.15) };
      copies = count;
    }
    if (expanded + copies > MAX_EXPANDED) break;
    expanded += copies;
    parts.push(part);
  }
  if (!parts.length) return null;
  return {
    name: String(raw.name ?? "").split(/\s+/).join(" ").trim().slice(0, 60) || "miniature",
    animation: MODEL_ANIMS.includes(raw.animation) ? raw.animation : "none",
    parts,
  };
}

/** Pure: every part a recipe expands to (repeats unrolled), each {..part, pos, rotY}. */
export function expandParts(recipe) {
  const out = [];
  for (const p of recipe.parts) {
    const r = p.repeat;
    if (!r) { out.push({ ...p, rotY: 0 }); continue; }
    for (let k = 0; k < r.count; k++) {
      if (r.mode === "ring") {
        const a = (k / r.count) * Math.PI * 2;
        out.push({ ...p, pos: [p.pos[0] + Math.cos(a) * r.radius, p.pos[1], p.pos[2] + Math.sin(a) * r.radius], rotY: -a });
      } else {
        out.push({ ...p, pos: [p.pos[0] + (k - (r.count - 1) / 2) * r.spacing, p.pos[1], p.pos[2]], rotY: 0 });
      }
    }
  }
  return out;
}

// ---------------------------------------------------------------------------------------------
// Procedural recipes

export function rng(seed) {
  let s = (Math.floor(Math.abs(seed) * 2654435761) ^ 0x9e3779b9) >>> 0 || 1;
  return () => {
    s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}

function hex([r, g, b]) {
  return "#" + [r, g, b].map((v) => Math.round(Math.min(255, Math.max(0, v))).toString(16).padStart(2, "0")).join("");
}
function shade(h, k) { // k > 1 lighter, < 1 darker
  const n = parseInt(h.slice(1), 16);
  return hex([(n >> 16) * k, ((n >> 8) & 255) * k, (n & 255) * k]);
}

const ROOFS = ["#3f6fc4", "#c8452e", "#2f7d4a", "#7a3fa8", "#d6a531", "#2a5d8f"];
const STONES = ["#cfc2a5", "#b8a98c", "#a8a29a", "#d8cbb0", "#9c958a"];
const WOODS = ["#9a6a3e", "#7d532e", "#a8743f"];
const BANNERS = ["#c8342b", "#e1b337", "#2f62b5", "#f2efe8", "#3d8a4a"];
const SCALES = ["#4f9a3a", "#b0392d", "#3a6fb0", "#6a3a8f", "#c78a1e", "#2f2f35"];
const LEAVES = ["#5f9a3a", "#4f8a2e", "#78a83f", "#3f7a36"];

function maker(seed) {
  const r = rng(seed);
  const api = {
    r,
    between: (a, b) => a + (b - a) * r(),
    pick: (arr) => arr[Math.floor(r() * arr.length)],
    chance: (p) => r() < p,
    parts: [],
    add(shape, size, pos, colour, material, extra = {}) {
      api.parts.push({ shape, size, pos, colour, material, ...extra });
    },
  };
  return api;
}

function ground(m, w, colour = m.pick(["#6f9e43", "#5f8f3a", "#7fa84a"])) {
  m.add("cylinder", [Math.min(1.2, w * 1.15), 0.05, Math.min(1.2, w * 0.9)], [0, 0, 0], colour, "leaf");
}

function flag(m, x, y, colour) {
  m.add("cylinder", [0.02, 0.22, 0.02], [x, y, 0], "#4a3524", "wood");
  m.add("box", [0.14, 0.08, 0.01], [x + 0.07, y + 0.13, 0], colour, "cloth", { anim: "sway" });
}

const GEN = {
  castle(m, w) {
    const stone = m.pick(STONES), roof = m.pick(ROOFS), banner = m.pick(BANNERS);
    ground(m, w);
    const kw = w * m.between(0.5, 0.65), kh = m.between(0.38, 0.5);
    m.add("box", [kw, kh, 0.4], [0, 0.05, 0], stone, "stone");
    m.add("box", [0.07, 0.07, 0.07], [0, 0.05 + kh, 0.17], stone, "stone", { repeat: { count: Math.max(3, Math.round(kw / 0.1)), mode: "line", spacing: kw / Math.max(3, Math.round(kw / 0.1)) } });
    const towers = m.chance(0.5) ? [-1, 1] : [-1, 0, 1];
    for (const side of towers) {
      const x = side * w * 0.42, th = side === 0 ? m.between(0.75, 0.95) : m.between(0.55, 0.75), tw = side === 0 ? 0.26 : 0.2;
      if (side === 0) m.add("box", [tw, th, tw], [0, 0.05, -0.05], stone, "stone");
      else m.add("cylinder", [tw, th, tw], [x, 0.05, 0], stone, "stone");
      m.add(side === 0 ? "pyramid" : "cone", [tw * 1.3, m.between(0.22, 0.34), tw * 1.3], [x, 0.05 + th, side === 0 ? -0.05 : 0], roof, "wood");
      m.add("box", [0.04, 0.07, 0.01], [x, 0.05 + th * 0.6, (side === 0 ? -0.05 : 0) + tw / 2], "#ffd36b", "glow");
      if (m.chance(0.7)) flag(m, x, 0.05 + th + 0.25, banner);
    }
    m.add("box", [0.13, 0.18, 0.02], [0, 0.05, 0.2], "#4a2f1b", "wood");
  },
  palace(m, w) {
    const wall = m.pick(["#f4ead2", "#efe0c0", "#e9e4f2"]), dome = m.pick(["#e0a92e", "#d8b24a", "#3f8fb0", "#c85a8a"]);
    ground(m, w);
    m.add("box", [w * 0.9, 0.32, 0.4], [0, 0.05, 0], wall, "stone");
    m.add("cylinder", [0.06, 0.28, 0.06], [0, 0.05, 0.21], wall, "stone", { repeat: { count: 5, mode: "line", spacing: w * 0.18 } });
    m.add("box", [w * 0.45, 0.2, 0.3], [0, 0.37, 0], wall, "stone");
    m.add("dome", [w * 0.42, m.between(0.25, 0.38), 0.3], [0, 0.57, 0], dome, "gold");
    m.add("sphere", [0.05, 0.05, 0.05], [0, 0.57 + 0.3, 0], "#f3c64a", "gold");
    for (const s of [-1, 1]) {
      m.add("cylinder", [0.12, 0.45, 0.12], [s * w * 0.42, 0.05, 0], wall, "stone");
      m.add("dome", [0.14, 0.12, 0.14], [s * w * 0.42, 0.5, 0], dome, "gold");
    }
    m.add("box", [0.12, 0.16, 0.02], [0, 0.05, 0.21], "#3c2a5a", "wood");
    m.add("box", [0.05, 0.06, 0.01], [0, 0.42, 0.16], "#ffd36b", "glow", { repeat: { count: 3, mode: "line", spacing: 0.1 } });
  },
  fortress(m, w) {
    const iron = m.pick(["#4a4750", "#3b3840", "#55505a"]), banner = m.pick(["#a8241d", "#6a1e5a", "#1e3a6a"]);
    ground(m, w, "#5a4a3a");
    m.add("box", [w * 0.95, 0.4, 0.42], [0, 0.05, 0], iron, "metal");
    m.add("cone", [0.08, 0.14, 0.08], [0, 0.45, 0.18], "#2b2930", "metal", { repeat: { count: Math.max(3, Math.round(w / 0.16)), mode: "line", spacing: w * 0.9 / Math.max(3, Math.round(w / 0.16)) } });
    m.add("box", [0.3, m.between(0.75, 0.95), 0.3], [0, 0.05, -0.05], iron, "metal");
    m.add("pyramid", [0.38, 0.25, 0.38], [0, 0.95, -0.05], "#2b2930", "metal");
    m.add("box", [0.1, 0.04, 0.01], [0, 0.7, 0.11], "#ff8a2a", "glow", { anim: "flicker" });
    for (const s of [-1, 1]) m.add("box", [0.1, 0.22, 0.01], [s * w * 0.28, 0.16, 0.215], banner, "cloth", { anim: "sway" });
    m.add("box", [0.14, 0.2, 0.02], [0, 0.05, 0.215], "#120d0b", "metal");
  },
  temple(m, w) {
    const st = m.pick(STONES);
    ground(m, w);
    m.add("box", [w * 0.95, 0.06, 0.5], [0, 0.05, 0], shade(st, 0.9), "stone");
    m.add("box", [w * 0.85, 0.06, 0.44], [0, 0.11, 0], st, "stone");
    m.add("cylinder", [0.07, 0.42, 0.07], [0, 0.17, 0.15], st, "stone", { repeat: { count: 4, mode: "line", spacing: w * 0.22 } });
    m.add("box", [w * 0.6, 0.38, 0.22], [0, 0.17, -0.05], "#3a2f22", "stone");
    m.add("box", [w * 0.9, 0.07, 0.46], [0, 0.59, 0], st, "stone");
    m.add("pyramid", [w * 0.85, 0.26, 0.44], [0, 0.66, 0], st, "stone");
    m.add("sphere", [0.08, 0.08, 0.08], [0, 0.92, 0], "#e7c25a", "gold");
    for (let i = 0; i < 3; i++) m.add("sphere", [0.09, 0.07, 0.05], [m.between(-w / 2, w / 2), m.between(0.2, 0.6), 0.2], m.pick(LEAVES), "leaf");
  },
  tower(m, w) {
    const st = m.pick(STONES), roof = m.pick(ROOFS);
    const tw = Math.min(0.42, Math.max(0.2, w * 0.55)), th = m.between(0.72, 0.92);
    ground(m, Math.max(w, 0.5));
    m.add(m.chance(0.7) ? "cylinder" : "box", [tw, th, tw], [0, 0.05, 0], st, "stone");
    m.add("cylinder", [tw * 1.25, 0.06, tw * 1.25], [0, 0.05 + th, 0], shade(st, 0.9), "stone");
    m.add("box", [0.06, 0.07, 0.06], [0, 0.11 + th, 0], st, "stone", { repeat: { count: m.chance(0.5) ? 6 : 8, mode: "ring", radius: tw * 0.55 } });
    if (m.chance(0.8)) m.add("cone", [tw * 1.35, m.between(0.25, 0.38), tw * 1.35], [0, 0.11 + th, 0], roof, "wood");
    m.add("box", [0.05, 0.08, 0.01], [0, 0.05 + th * 0.55, tw / 2], "#ffd36b", "glow");
    m.add("box", [0.05, 0.08, 0.01], [0, 0.05 + th * 0.25, tw / 2], "#2a1c12", "wood");
    flag(m, 0, Math.min(1.15, 0.45 + th), m.pick(BANNERS));
  },
  beacon(m, w) {
    const st = m.pick(STONES);
    const pw = Math.min(0.36, Math.max(0.18, w * 0.5)), ph = m.between(0.55, 0.75);
    ground(m, Math.max(w, 0.5));
    m.add("cylinder", [pw, ph, pw], [0, 0.05, 0], st, "stone");
    m.add("cylinder", [pw * 1.6, 0.08, pw * 1.6], [0, 0.05 + ph, 0], "#5a4632", "metal");
    m.add("cone", [pw * 1.1, m.between(0.22, 0.32), pw * 1.1], [0, 0.13 + ph, 0], "#ff8a2a", "glow", { anim: "flicker" });
    m.add("cone", [pw * 0.6, m.between(0.16, 0.24), pw * 0.6], [0, 0.13 + ph, 0.02], "#ffe08a", "glow", { anim: "flicker" });
  },
  village(m, w) {
    ground(m, w);
    const n = w > 0.8 ? 3 : 2;
    for (let i = 0; i < n; i++) {
      const x = (i - (n - 1) / 2) * (w / n), hw = Math.min(0.32, w / n * 0.85), hh = m.between(0.22, 0.34), z = m.between(-0.12, 0.12);
      const roof = m.pick(["#c8452e", "#d9a84a", "#7a5a3a", "#3f6fc4"]);
      m.add("box", [hw, hh, 0.26], [x, 0.05, z], m.pick(["#f4e6c6", "#e8d8b0", "#d9c9a8"]), "stone");
      m.add("wedge", [hw * 1.15, m.between(0.16, 0.24), 0.32], [x, 0.05 + hh, z], roof, "wood");
      m.add("box", [0.05, 0.05, 0.01], [x + hw * 0.22, 0.05 + hh * 0.55, z + 0.13], "#ffd36b", "glow");
      m.add("box", [0.06, 0.11, 0.01], [x - hw * 0.18, 0.05, z + 0.13], "#5a3a22", "wood");
      if (i === 0 && m.chance(0.7)) m.add("box", [0.05, 0.14, 0.05], [x + hw * 0.3, 0.05 + hh + 0.06, z - 0.05], "#8a7a66", "stone");
    }
  },
  tree(m, w) {
    ground(m, w);
    const n = w > 0.7 ? 3 : m.chance(0.5) ? 1 : 2;
    for (let i = 0; i < n; i++) {
      const x = (i - (n - 1) / 2) * (w / Math.max(n, 1)) * 0.8, s = m.between(0.8, 1.1) * (i === Math.floor(n / 2) ? 1 : 0.8);
      const leaf = m.pick(LEAVES);
      m.add("cylinder", [0.07 * s, 0.35 * s, 0.07 * s], [x, 0.05, m.between(-0.1, 0.1)], m.pick(WOODS), "wood");
      if (m.chance(0.5)) {
        m.add("cone", [0.42 * s, 0.4 * s, 0.42 * s], [x, 0.28 * s, 0], leaf, "leaf");
        m.add("cone", [0.32 * s, 0.34 * s, 0.32 * s], [x, 0.52 * s, 0], shade(leaf, 1.12), "leaf");
      } else {
        m.add("sphere", [0.44 * s, 0.4 * s, 0.4 * s], [x, 0.3 * s, 0], leaf, "leaf", { anim: "sway" });
        m.add("sphere", [0.3 * s, 0.28 * s, 0.28 * s], [x + 0.08 * s, 0.6 * s, 0.03], shade(leaf, 1.15), "leaf");
      }
    }
    if (m.chance(0.5)) m.add("sphere", [0.04, 0.04, 0.04], [m.between(-w / 3, w / 3), 0.45, 0.2], "#c8342b", "glow");
  },
  dragon(m, w) {
    const sc = m.pick(SCALES), wing = m.pick(["#b44b3a", "#6a2018", "#3a3f6a", "#7a5a2a"]), belly = "#e8d59a";
    const L = Math.min(1.0, Math.max(0.5, w));
    m.add("cylinder", [L * 1.1, 0.04, 0.6], [0, 0, 0], "#6b5a45", "stone");
    m.add("sphere", [L * 0.62, 0.3, 0.32], [0, 0.12, 0], sc, "scale");
    m.add("sphere", [L * 0.4, 0.16, 0.1], [L * 0.04, 0.14, 0.12], belly, "scale");
    m.add("cylinder", [0.11, 0.34, 0.11], [L * 0.28, 0.3, 0], sc, "scale", { rot: [0, 0, -35] });
    m.add("box", [0.2, 0.14, 0.15], [L * 0.42, 0.55, 0], sc, "scale");
    m.add("box", [0.12, 0.07, 0.1], [L * 0.54, 0.55, 0], shade(sc, 0.85), "scale");
    m.add("cone", [0.04, 0.12, 0.04], [L * 0.4, 0.69, -0.04], "#e6d7a4", "stone", { repeat: { count: 2, mode: "line", spacing: 0.08 }, rot: [0, 0, 20] });
    m.add("sphere", [0.035, 0.035, 0.035], [L * 0.48, 0.62, 0.075], "#ffd93a", "glow");
    const span = m.between(0.42, 0.6);
    for (const s of [-1, 1]) m.add("cone", [span, 0.36, 0.03], [-L * 0.05, 0.3, s * 0.1], wing, "cloth", { rot: [s * 30, 0, 35], anim: "flap" });
    m.add("cone", [0.1, 0.45, 0.1], [-L * 0.42, 0.14, 0], sc, "scale", { rot: [0, 0, 70] });
    m.add("cylinder", [0.07, 0.16, 0.07], [0, 0.02, 0.1], shade(sc, 0.8), "scale", { repeat: { count: 2, mode: "line", spacing: L * 0.4 } });
    m.add("cylinder", [0.07, 0.16, 0.07], [0, 0.02, -0.1], shade(sc, 0.8), "scale", { repeat: { count: 2, mode: "line", spacing: L * 0.4 } });
  },
  beast(m, w) {
    const fur = m.pick(["#8f877f", "#6b625a", "#b9b3ad", "#5a4a3a"]);
    const n = w > 0.9 ? 2 : 1;
    m.add("cylinder", [Math.min(1.2, w * 1.1), 0.04, 0.6], [0, 0, 0], "#6f9a44", "leaf");
    for (let i = 0; i < n; i++) {
      const x = (i - (n - 1) / 2) * 0.55, z = i ? -0.12 : 0.06, s = i ? 0.85 : 1;
      m.add("sphere", [0.44 * s, 0.22 * s, 0.22 * s], [x, 0.13 * s, z], fur, "scale");
      m.add("box", [0.18 * s, 0.16 * s, 0.16 * s], [x + 0.24 * s, 0.24 * s, z], fur, "scale");
      m.add("box", [0.1 * s, 0.07 * s, 0.09 * s], [x + 0.35 * s, 0.25 * s, z], shade(fur, 0.8), "scale");
      m.add("cone", [0.05 * s, 0.08 * s, 0.05 * s], [x + 0.22 * s, 0.4 * s, z], fur, "scale", { repeat: { count: 2, mode: "line", spacing: 0.08 * s } });
      m.add("sphere", [0.03, 0.03, 0.03], [x + 0.32 * s, 0.32 * s, z + 0.08 * s], "#ffd23a", "glow");
      m.add("cylinder", [0.06 * s, 0.16 * s, 0.06 * s], [x, 0.02, z + 0.07], shade(fur, 0.85), "scale", { repeat: { count: 2, mode: "line", spacing: 0.28 * s } });
      m.add("cylinder", [0.06 * s, 0.16 * s, 0.06 * s], [x, 0.02, z - 0.07], shade(fur, 0.85), "scale", { repeat: { count: 2, mode: "line", spacing: 0.28 * s } });
      m.add("cone", [0.07 * s, 0.24 * s, 0.07 * s], [x - 0.24 * s, 0.22 * s, z], fur, "scale", { rot: [0, 0, 60], anim: "sway" });
    }
  },
  treasure(m, w) {
    const wood = m.pick(WOODS);
    m.add("cylinder", [Math.min(1.2, w), 0.04, 0.6], [0, 0, 0], "#6a5a40", "stone");
    m.add("box", [0.5, 0.26, 0.32], [0, 0.04, 0], wood, "wood");
    m.add("box", [0.52, 0.04, 0.34], [0, 0.16, 0], "#c9952c", "gold");
    m.add("box", [0.5, 0.14, 0.32], [0, 0.3, -0.12], wood, "wood", { rot: [-55, 0, 0] });
    m.add("dome", [0.44, 0.1, 0.26], [0, 0.3, 0], "#f0bb2e", "gold");
    m.add("sphere", [0.06, 0.03, 0.06], [0.32, 0.04, 0.15], "#f0bb2e", "gold", { repeat: { count: 4, mode: "line", spacing: 0.08 } });
    m.add("pyramid", [0.07, 0.1, 0.07], [m.between(-0.15, 0.15), 0.36, 0.05], m.pick(["#e04a6a", "#4ac0e0", "#6ae04a"]), "crystal", { anim: "pulse" });
  },
  cave(m, w) {
    const rock = m.pick(["#8a7f70", "#6c6253", "#7a7068"]);
    m.add("dome", [Math.min(1.2, w), m.between(0.6, 0.8), 0.7], [0, 0, 0], rock, "stone");
    m.add("dome", [0.4, 0.45, 0.06], [0, 0, 0.33], "#0a0604", "stone");
    m.add("cone", [0.06, 0.12, 0.06], [0, 0.32, 0.33], rock, "stone", { rot: [180, 0, 0], repeat: { count: 3, mode: "line", spacing: 0.1 } });
    m.add("sphere", [0.03, 0.03, 0.03], [0, 0.18, 0.36], "#ff9a3a", "glow", { repeat: { count: 2, mode: "line", spacing: 0.07 }, anim: "pulse" });
    for (let i = 0; i < 3; i++) m.add("sphere", [m.between(0.12, 0.2), 0.1, 0.12], [m.between(-w / 2, w / 2), m.between(0.3, 0.6), 0.2], m.pick(LEAVES), "leaf");
  },
  crystal(m, w) {
    const c = m.pick(["#7ec8f0", "#b78cf0", "#7ef0c0", "#f07ec0"]);
    m.add("cylinder", [Math.min(1.2, w), 0.05, 0.6], [0, 0, 0], "#5a5470", "stone");
    const n = 3 + Math.floor(m.r() * 3);
    for (let i = 0; i < n; i++) {
      const tall = i === 0 ? m.between(0.75, 1.0) : m.between(0.3, 0.6);
      m.add("pyramid", [m.between(0.12, 0.2), tall, m.between(0.12, 0.2)], [i === 0 ? 0 : m.between(-w / 2.5, w / 2.5), 0.04, m.between(-0.1, 0.1)],
        i % 2 ? shade(c, 1.15) : c, "crystal", { rot: [m.between(-15, 15), m.between(0, 90), m.between(-20, 20)], anim: i === 0 ? "pulse" : "none" });
    }
  },
  ship(m, w) {
    const wood = m.pick(WOODS), sail = m.pick(["#f6efe0", "#e8dcc0", "#d9c4a0"]);
    m.add("cylinder", [Math.min(1.2, w * 1.1), 0.03, 0.5], [0, 0, 0], "#2d6f9e", "water");
    m.add("box", [w * 0.85, 0.14, 0.28], [0, 0.03, 0], wood, "wood");
    m.add("wedge", [0.16, 0.14, 0.28], [w * 0.47, 0.03, 0], wood, "wood");
    m.add("cylinder", [0.03, 0.75, 0.03], [0.05, 0.17, 0], "#4a3524", "wood");
    m.add("box", [0.34, 0.38, 0.02], [0.05, 0.32, 0.03], sail, "cloth", { anim: "sway" });
    if (w > 0.6) {
      m.add("cylinder", [0.03, 0.55, 0.03], [-w * 0.25, 0.17, 0], "#4a3524", "wood");
      m.add("box", [0.24, 0.26, 0.02], [-w * 0.25, 0.3, 0.03], sail, "cloth", { anim: "sway" });
    }
    m.add("box", [0.14, 0.07, 0.01], [0.12, 0.88, 0], m.pick(BANNERS), "cloth", { anim: "sway" });
  },
  mountain(m, w) {
    const rock = m.pick(["#8f857a", "#7a7068", "#9c8f80"]);
    m.add("cylinder", [Math.min(1.2, w * 1.1), 0.04, 0.6], [0, 0, 0], "#4d6b30", "leaf");
    m.add("cone", [w * 0.8, m.between(0.8, 1.0), 0.6], [-w * 0.08, 0.04, 0], rock, "stone");
    m.add("cone", [w * 0.24, 0.24, 0.2], [-w * 0.08, m.between(0.62, 0.78), 0], "#f6f8fb", "stone");
    m.add("cone", [w * 0.55, m.between(0.5, 0.65), 0.45], [w * 0.28, 0.04, -0.08], shade(rock, 0.85), "stone");
    m.add("cone", [0.08, 0.16, 0.08], [-w * 0.4, 0.04, 0.22], m.pick(LEAVES), "leaf", { repeat: { count: 3, mode: "line", spacing: 0.1 } });
  },
  monolith(m, w) {
    const st = m.pick(["#8d857a", "#7d7568", "#6a6560"]);
    ground(m, Math.max(w, 0.5));
    m.add("box", [Math.min(0.5, Math.max(0.18, w * 0.5)), m.between(0.75, 1.0), 0.16], [0, 0.05, 0], st, "stone", { rot: [0, m.between(-15, 15), m.between(-4, 4)] });
    m.add("box", [0.06, 0.06, 0.01], [0, 0.35, 0.085], m.pick(["#7fd6ff", "#9aff7f", "#ffb37f"]), "glow", { repeat: { count: 3, mode: "line", spacing: 0.09 }, anim: "pulse" });
  },
};

export const GENERATOR_KEYS = Object.keys(GEN);

const CREATURES = new Set(["dragon", "beast"]);

/**
 * Pure: a procedural recipe for art `key` (sprites.js artFor), seeded, shaped to `aspect` (width / height of
 * the real object on screen).
 */
export function proceduralRecipe(key, seed = 0, aspect = 1) {
  const gen = GEN[key] ?? GEN.monolith;
  const m = maker(seed + GENERATOR_KEYS.indexOf(key) * 7919);
  const w = Math.min(1.5, Math.max(0.35, Number(aspect) || 1));
  gen(m, w);
  return normaliseRecipe({
    name: `${key} #${Math.floor(seed * 1000) % 1000}`,
    animation: CREATURES.has(key) ? m.pick(["breathe", "bob"]) : "none",
    parts: m.parts,
  });
}
