// Terrain layer (T86, whitepaper §7.13, §7.5): fills the map with animated ground in the world's style.
//
// Style from setting keywords: ocean/sea → water, volcanic/lava → lava, snow/ice → snow, space → stars,
// city/neon → grid, jungle/forest → jungle grass, royal/court → marble, kingdom/medieval → meadow grass,
// anything else → parchment. Everything is procedural (no image assets) and tinted by the palette.
// The static detail is rendered once per world/size into an offscreen canvas; each frame only adds cheap
// animated strokes and particles. `open_regions` are drawn slightly brighter. Beyond the table edge sits
// "the edge of the world": a dark void with a jagged cliff rim.

const STYLES = [
  ["water", ["ocean", "sea", "coast", "island", "harbour", "reef", "pirate", "shanty"]],
  ["lava", ["volcan", "lava", "inferno", "ash", "fire", "wasteland", "desert"]],
  ["snow", ["snow", "ice", "frost", "frozen", "winter", "arctic", "glacier", "tundra"]],
  ["stars", ["space", "station", "orbit", "galaxy", "cosmic", "star"]],
  ["grid", ["neon", "city", "cyber", "synth", "metropolis", "future"]],
  ["jungle", ["jungle", "rainforest", "forest", "swamp", "woods", "grove", "tropical"]],
  ["marble", ["royal", "court", "palace", "throne", "baroque"]],
  ["meadow", ["kingdom", "castle", "medieval", "village", "realm", "meadow", "knight"]],
];

// Each style's own colours; the world palette is blended in (TINT) so styles stay recognisable.
const BASE = {
  water: { a: [16, 52, 92], b: [34, 96, 140], c: [210, 235, 245] },
  lava: { a: [28, 20, 18], b: [70, 40, 30], c: [255, 120, 30] },
  snow: { a: [40, 56, 92], b: [196, 210, 232], c: [255, 255, 255] },
  stars: { a: [8, 8, 24], b: [60, 40, 110], c: [230, 230, 255] },
  grid: { a: [12, 8, 26], b: [255, 60, 170], c: [60, 200, 255] },
  jungle: { a: [18, 52, 26], b: [46, 104, 44], c: [220, 240, 120] },
  marble: { a: [196, 186, 170], b: [232, 226, 214], c: [150, 120, 160] },
  meadow: { a: [84, 128, 56], b: [150, 170, 80], c: [250, 240, 190] },
  parchment: { a: [214, 196, 158], b: [186, 160, 116], c: [120, 90, 60] },
};
const TINT = 0.35;
const DARK = new Set(["grid", "stars", "lava"]); // keep their dark base dark

export function styleFor(world) {
  const info = world?.world ?? {};
  for (const field of ["setting", "name"]) {
    const text = String(info[field] ?? "").toLowerCase();
    if (!text) continue;
    for (const [style, keys] of STYLES) if (keys.some((k) => text.includes(k))) return style;
  }
  return "parchment";
}

// ---- small helpers ---------------------------------------------------------------------------------------

const mix = (p, q, k) => p.map((v, i) => Math.round(v + (q[i] - v) * k));
const rgba = (c, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
const clamp01 = (v) => Math.max(0, Math.min(1, v));

function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hash(str) {
  let h = 2166136261;
  for (const ch of String(str)) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return h >>> 0;
}

function makeCanvas(w, h) {
  if (typeof OffscreenCanvas !== "undefined") return new OffscreenCanvas(w, h);
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  return c;
}

function colours(style, palette) {
  const base = BASE[style];
  const p = palette ?? [];
  return {
    a: p[0] ? mix(base.a, p[0], DARK.has(style) ? TINT * 0.3 : TINT) : base.a,
    b: p[1] ? mix(base.b, p[1], TINT) : base.b,
    c: p[2] ? mix(base.c, p[2], TINT * 0.6) : base.c,
  };
}

// ---- static textures (drawn once per world and size) --------------------------------------------------------

const TEXTURES = {
  water(g, w, h, c, r) {
    const grad = g.createLinearGradient(0, 0, w, h);
    grad.addColorStop(0, rgba(c.a));
    grad.addColorStop(1, rgba(mix(c.a, c.b, 0.6)));
    g.fillStyle = grad;
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 40; i++) {
      const x = r() * w, y = r() * h, rad = (0.05 + r() * 0.15) * w;
      const rg = g.createRadialGradient(x, y, 0, x, y, rad);
      rg.addColorStop(0, rgba(r() > 0.5 ? c.b : mix(c.a, [0, 0, 0], 0.4), 0.25));
      rg.addColorStop(1, rgba(c.a, 0));
      g.fillStyle = rg;
      g.fillRect(x - rad, y - rad, rad * 2, rad * 2);
    }
  },
  lava(g, w, h, c, r, glow) {
    g.fillStyle = rgba(c.a);
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 300; i++) { // crust plates
      g.fillStyle = rgba(mix(c.a, c.b, r()), 0.5);
      const x = r() * w, y = r() * h, s = (0.02 + r() * 0.06) * w;
      g.beginPath();
      for (let k = 0; k < 6; k++) {
        const an = (k / 6) * Math.PI * 2 + r() * 0.5;
        g.lineTo(x + Math.cos(an) * s * (0.6 + r() * 0.5), y + Math.sin(an) * s * (0.6 + r() * 0.5));
      }
      g.fill();
    }
    // the crack network goes on the separate glow canvas, so it can pulse
    const gg = glow.getContext("2d");
    gg.strokeStyle = rgba(c.c);
    gg.lineCap = "round";
    for (let i = 0; i < 26; i++) {
      let x = r() * w, y = r() * h, an = r() * Math.PI * 2;
      gg.lineWidth = 1 + r() * 3;
      gg.beginPath();
      gg.moveTo(x, y);
      for (let k = 0; k < 14; k++) {
        an += (r() - 0.5) * 1.2;
        x += Math.cos(an) * w * 0.03;
        y += Math.sin(an) * w * 0.03;
        gg.lineTo(x, y);
      }
      gg.stroke();
    }
  },
  snow(g, w, h, c, r) {
    const grad = g.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, rgba(mix(c.a, c.b, 0.55)));
    grad.addColorStop(1, rgba(mix(c.a, c.b, 0.8)));
    g.fillStyle = grad;
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 60; i++) { // drifts
      const x = r() * w, y = r() * h, rx = (0.06 + r() * 0.12) * w, ry = rx * (0.25 + r() * 0.2);
      g.fillStyle = rgba(c.c, 0.07 + r() * 0.1);
      g.beginPath();
      g.ellipse(x, y, rx, ry, (r() - 0.5) * 0.4, 0, Math.PI * 2);
      g.fill();
      g.fillStyle = rgba(c.a, 0.12);
      g.beginPath();
      g.ellipse(x + rx * 0.1, y + ry * 0.7, rx * 0.9, ry * 0.4, 0, 0, Math.PI * 2);
      g.fill();
    }
  },
  stars(g, w, h, c, r) {
    g.fillStyle = rgba(c.a);
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 6; i++) { // nebula
      const x = r() * w, y = r() * h, rad = (0.2 + r() * 0.3) * w;
      const rg = g.createRadialGradient(x, y, 0, x, y, rad);
      rg.addColorStop(0, rgba(i % 2 ? c.b : mix(c.b, c.c, 0.3), 0.22));
      rg.addColorStop(1, rgba(c.b, 0));
      g.fillStyle = rg;
      g.fillRect(x - rad, y - rad, rad * 2, rad * 2);
    }
    for (let i = 0; i < 320; i++) {
      g.fillStyle = rgba(c.c, 0.2 + r() * 0.6);
      const s = r() < 0.9 ? 1 : 2;
      g.fillRect(r() * w, r() * h, s, s);
    }
  },
  grid(g, w, h, c) {
    const grad = g.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, rgba(c.a));
    grad.addColorStop(1, rgba(mix(c.a, c.b, 0.12)));
    g.fillStyle = grad;
    g.fillRect(0, 0, w, h);
  },
  jungle(g, w, h, c, r) {
    g.fillStyle = rgba(c.a);
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 900; i++) { // leaves
      const x = r() * w, y = r() * h, s = (0.008 + r() * 0.022) * w;
      g.fillStyle = rgba(mix(c.a, c.b, 0.3 + r() * 0.7), 0.55 + r() * 0.4);
      g.beginPath();
      g.ellipse(x, y, s, s * 0.45, r() * Math.PI, 0, Math.PI * 2);
      g.fill();
    }
  },
  meadow(g, w, h, c, r) {
    g.fillStyle = rgba(c.a);
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 22; i++) { // fields
      g.save();
      g.translate(r() * w, r() * h);
      g.rotate((r() - 0.5) * 0.6);
      g.fillStyle = rgba(mix(c.a, c.b, r()), 0.55);
      const fw = (0.1 + r() * 0.2) * w, fh = (0.06 + r() * 0.12) * h;
      g.fillRect(-fw / 2, -fh / 2, fw, fh);
      g.strokeStyle = rgba(mix(c.a, [0, 0, 0], 0.3), 0.25);
      g.lineWidth = 1;
      for (let k = -fh / 2 + 4; k < fh / 2; k += 6) { g.beginPath(); g.moveTo(-fw / 2, k); g.lineTo(fw / 2, k); g.stroke(); }
      g.restore();
    }
    g.strokeStyle = rgba(mix(c.a, [0, 0, 0], 0.35), 0.5);
    g.lineWidth = 1.2;
    for (let i = 0; i < 500; i++) { // grass tufts
      const x = r() * w, y = r() * h;
      g.beginPath();
      g.moveTo(x - 3, y - 4); g.lineTo(x, y); g.lineTo(x + 3, y - 5);
      g.stroke();
    }
  },
  marble(g, w, h, c, r) {
    const n = 14, tile = Math.max(w, h) / n;
    for (let i = 0; i * tile < w; i++) {
      for (let j = 0; j * tile < h; j++) {
        g.fillStyle = rgba((i + j) % 2 ? c.b : mix(c.b, mix(c.a, c.c, 0.25), 0.45));
        g.fillRect(i * tile, j * tile, tile + 1, tile + 1);
      }
    }
    g.strokeStyle = rgba(mix(c.c, [0, 0, 0], 0.3), 0.18);
    for (let i = 0; i < 40; i++) { // veins
      g.lineWidth = 0.5 + r() * 1.5;
      g.beginPath();
      const x = r() * w, y = r() * h;
      g.moveTo(x, y);
      g.bezierCurveTo(x + (r() - 0.5) * w * 0.3, y + (r() - 0.5) * h * 0.3, x + (r() - 0.5) * w * 0.3, y + (r() - 0.5) * h * 0.3, x + (r() - 0.5) * w * 0.4, y + (r() - 0.5) * h * 0.4);
      g.stroke();
    }
    g.strokeStyle = rgba(c.c, 0.35);
    g.lineWidth = Math.max(4, w * 0.012);
    g.strokeRect(w * 0.04, h * 0.04, w * 0.92, h * 0.92);
  },
  parchment(g, w, h, c, r) {
    g.fillStyle = rgba(c.a);
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 1500; i++) {
      g.fillStyle = rgba(mix(c.a, c.b, r()), 0.35);
      g.fillRect(r() * w, r() * h, 2, 2);
    }
    g.strokeStyle = rgba(c.c, 0.18);
    g.lineWidth = 1;
    for (let k = 0; k < 4; k++) { // contour lines
      const cx = r() * w, cy = r() * h;
      for (let ring = 1; ring < 6; ring++) {
        g.beginPath();
        for (let an = 0; an <= Math.PI * 2 + 0.01; an += 0.2) {
          const rad = ring * w * 0.025 * (1 + 0.15 * Math.sin(an * 3 + k));
          g.lineTo(cx + Math.cos(an) * rad, cy + Math.sin(an) * rad * 0.7);
        }
        g.stroke();
      }
    }
  },
};

// ---- per-frame animation -------------------------------------------------------------------------------------

function particles(seed, n) {
  const r = rng(seed);
  return Array.from({ length: n }, () => ({ x: r(), y: r(), s: r(), p: r() * Math.PI * 2 }));
}
const P = {
  waves: particles(11, 70), flakes: particles(12, 170), embers: particles(13, 40), flies: particles(14, 28),
  twinkle: particles(15, 70), motes: particles(16, 40), pools: particles(17, 6),
};

const ANIMATE = {
  water(g, w, h, c, t, beat) {
    g.strokeStyle = rgba(c.c, 0.18);
    g.lineWidth = 1.5;
    for (let i = 0; i < 6; i++) { // caustic swells
      g.beginPath();
      for (let x = 0; x <= w; x += 12) {
        const y = (i + 0.5) / 6 * h + Math.sin(x / w * 9 + t * 0.8 + i * 1.7) * h * 0.02;
        if (x === 0) g.moveTo(x, y); else g.lineTo(x, y);
      }
      g.stroke();
    }
    g.lineWidth = 2;
    for (const p of P.waves) { // little wave crests drifting
      const x = ((p.x + t * 0.01 * (0.5 + p.s)) % 1) * w;
      const y = p.y * h + Math.sin(t * 1.5 + p.p) * 3;
      const a = 0.25 + 0.35 * Math.max(0, Math.sin(t * 1.2 + p.p)) + 0.25 * beat;
      const s = 6 + p.s * 10;
      g.strokeStyle = rgba(c.c, clamp01(a));
      g.beginPath();
      g.arc(x, y, s, Math.PI * 1.15, Math.PI * 1.85);
      g.stroke();
    }
  },
  lava(g, w, h, c, t, beat, tex) {
    for (const p of P.pools) {
      const x = p.x * w, y = p.y * h, rad = (0.06 + 0.04 * p.s) * w * (1 + 0.15 * Math.sin(t * 0.8 + p.p) + 0.15 * beat);
      const rg = g.createRadialGradient(x, y, 0, x, y, rad);
      rg.addColorStop(0, rgba([255, 200, 80], 0.5));
      rg.addColorStop(0.5, rgba(c.c, 0.35));
      rg.addColorStop(1, rgba(c.c, 0));
      g.fillStyle = rg;
      g.fillRect(x - rad, y - rad, rad * 2, rad * 2);
    }
    g.save();
    g.globalCompositeOperation = "lighter";
    g.globalAlpha = clamp01(0.45 + 0.25 * Math.sin(t * 1.3) + 0.4 * beat);
    g.drawImage(tex.glow, 0, 0, w, h);
    g.restore();
    for (const p of P.embers) { // rising embers
      const life = (t * (0.08 + p.s * 0.1) + p.p) % 1;
      const x = p.x * w + Math.sin(t + p.p) * 8;
      const y = h - life * h;
      g.fillStyle = rgba([255, 170, 60], clamp01(1 - life) * 0.9);
      g.fillRect(x, y, 2.5, 2.5);
    }
  },
  snow(g, w, h, c, t, beat) {
    g.fillStyle = rgba(c.c, 0.9);
    for (const p of P.flakes) {
      const y = ((p.y + t * (0.02 + p.s * 0.03)) % 1) * h;
      const x = ((p.x + Math.sin(t * 0.6 + p.p) * 0.015) % 1) * w;
      const s = 1.5 + p.s * 2.5 + beat;
      g.beginPath();
      g.arc(x, y, s, 0, Math.PI * 2);
      g.fill();
    }
  },
  stars(g, w, h, c, t, beat) {
    for (const p of P.twinkle) {
      const a = clamp01(0.3 + 0.7 * Math.abs(Math.sin(t * (0.5 + p.s) + p.p)) + 0.3 * beat);
      g.fillStyle = rgba(c.c, a);
      const x = p.x * w, y = p.y * h, s = 1 + p.s * 2;
      g.fillRect(x - s / 2, y - s / 2, s, s);
      if (p.s > 0.85) { g.fillRect(x - 4, y - 0.5, 8, 1); g.fillRect(x - 0.5, y - 4, 1, 8); }
    }
    const shoot = (t % 9) / 9; // a shooting star every 9 s
    if (shoot < 0.12) {
      const k = shoot / 0.12, x = w * (0.1 + 0.8 * k), y = h * (0.15 + 0.3 * k);
      const grad = g.createLinearGradient(x - 80, y - 30, x, y);
      grad.addColorStop(0, rgba(c.c, 0));
      grad.addColorStop(1, rgba(c.c, 0.9));
      g.strokeStyle = grad;
      g.lineWidth = 2;
      g.beginPath(); g.moveTo(x - 80, y - 30); g.lineTo(x, y); g.stroke();
    }
  },
  grid(g, w, h, c, t, beat, _tex, unit) {
    const step = Math.max(24, 46 * unit);
    const off = (t * 18) % step;
    for (const [col, width, alpha] of [[c.b, 6, 0.08 + 0.1 * beat], [c.b, 1.5, 0.45 + 0.4 * beat]]) {
      g.strokeStyle = rgba(col, clamp01(alpha));
      g.lineWidth = width;
      g.beginPath();
      for (let x = -step + off; x < w + step; x += step) { g.moveTo(x, 0); g.lineTo(x, h); }
      for (let y = -step + off; y < h + step; y += step) { g.moveTo(0, y); g.lineTo(w, y); }
      g.stroke();
    }
    g.fillStyle = rgba(c.c, 0.95); // data pulses running along the lines
    for (let i = 0; i < 10; i++) {
      const lane = Math.floor((i * 7.3) % Math.max(1, Math.floor(h / step)));
      const y = lane * step + off;
      const x = ((t * (0.15 + (i % 3) * 0.07) + i * 0.13) % 1) * w;
      g.fillRect(x - 6, y - 1.5, 12, 3);
    }
  },
  jungle(g, w, h, c, t, beat) {
    for (let i = 0; i < 3; i++) { // light shafts
      const x = ((t * 0.02 + i / 3) % 1.4 - 0.2) * w;
      const grad = g.createLinearGradient(x, 0, x + w * 0.15, h);
      grad.addColorStop(0, rgba(c.c, 0));
      grad.addColorStop(0.5, rgba(c.c, 0.07));
      grad.addColorStop(1, rgba(c.c, 0));
      g.fillStyle = grad;
      g.beginPath();
      g.moveTo(x, 0); g.lineTo(x + w * 0.08, 0); g.lineTo(x + w * 0.3, h); g.lineTo(x + w * 0.22, h);
      g.fill();
    }
    for (const p of P.flies) { // fireflies
      const x = (p.x + Math.sin(t * 0.3 + p.p) * 0.03) * w;
      const y = (p.y + Math.cos(t * 0.4 + p.p * 2) * 0.03) * h;
      const a = clamp01(0.2 + 0.8 * Math.max(0, Math.sin(t * 2 + p.p * 3)) + 0.3 * beat);
      const rg = g.createRadialGradient(x, y, 0, x, y, 7);
      rg.addColorStop(0, rgba(c.c, a));
      rg.addColorStop(1, rgba(c.c, 0));
      g.fillStyle = rg;
      g.fillRect(x - 7, y - 7, 14, 14);
    }
  },
  meadow(g, w, h, c, t) {
    const k = (t / 7) % 1; // a breeze sweeping across
    const x = (k * 1.6 - 0.3) * w;
    const grad = g.createLinearGradient(x - w * 0.15, 0, x + w * 0.15, h * 0.3);
    grad.addColorStop(0, rgba(c.c, 0));
    grad.addColorStop(0.5, rgba(c.c, 0.12));
    grad.addColorStop(1, rgba(c.c, 0));
    g.fillStyle = grad;
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 2; i++) { // cloud shadows
      const cx = ((t * 0.012 + i * 0.55) % 1.4 - 0.2) * w, cy = (0.3 + 0.4 * i) * h;
      const rg = g.createRadialGradient(cx, cy, 0, cx, cy, w * 0.18);
      rg.addColorStop(0, "rgba(0,0,0,0.16)");
      rg.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = rg;
      g.fillRect(cx - w * 0.2, cy - w * 0.2, w * 0.4, w * 0.4);
    }
  },
  marble(g, w, h, c, t) {
    const k = (t / 9) % 1; // sheen across the polished floor
    const x = (k * 1.8 - 0.4) * w;
    const grad = g.createLinearGradient(x, 0, x + w * 0.25, h);
    grad.addColorStop(0, "rgba(255,255,255,0)");
    grad.addColorStop(0.5, "rgba(255,255,255,0.16)");
    grad.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = grad;
    g.fillRect(0, 0, w, h);
    for (const p of P.motes) {
      g.fillStyle = rgba([255, 240, 200], 0.25 + 0.25 * Math.sin(t + p.p));
      g.fillRect((p.x + Math.sin(t * 0.1 + p.p) * 0.02) * w, ((p.y + t * 0.004) % 1) * h, 2, 2);
    }
  },
  parchment(g, w, h, c, t) {
    const a = 0.12 + 0.04 * Math.sin(t * 7) * Math.sin(t * 3.1); // candle flicker
    const rg = g.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.3, w / 2, h / 2, Math.max(w, h) * 0.75);
    rg.addColorStop(0, "rgba(0,0,0,0)");
    rg.addColorStop(1, `rgba(60,30,10,${a + 0.2})`);
    g.fillStyle = rg;
    g.fillRect(0, 0, w, h);
  },
};

// ---- the edge of the world -------------------------------------------------------------------------------------

function drawEdge(ctx, rect, c, rim, t) {
  const { viewW, viewH } = rect;
  const rg = ctx.createRadialGradient(viewW / 2, viewH / 2, Math.min(rect.w, rect.h) * 0.4, viewW / 2, viewH / 2, Math.max(viewW, viewH) * 0.75);
  rg.addColorStop(0, rgba(mix(c.a, [0, 0, 0], 0.6)));
  rg.addColorStop(1, "rgb(4,4,6)");
  ctx.fillStyle = rg;
  ctx.fillRect(0, 0, viewW, viewH);
  // mist drifting off the edge
  ctx.fillStyle = rgba(mix(c.b, [255, 255, 255], 0.3), 0.05 + 0.03 * Math.sin(t * 0.7));
  ctx.fillRect(rect.x - 30, rect.y - 30, rect.w + 60, rect.h + 60);
  // jagged cliff rim
  const rock = mix(mix(c.a, [70, 55, 40], 0.6), [0, 0, 0], 0.25);
  ctx.fillStyle = rgba(rock);
  ctx.beginPath();
  for (const [u, v, dx, dy] of rim) ctx.lineTo(rect.x + u * rect.w + dx, rect.y + v * rect.h + dy);
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = rgba(mix(rock, [255, 255, 255], 0.15));
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

function makeRim(seed) {
  // Points around the table as [u, v, dx, dy]: a spot on the edge (u, v in 0..1) pushed outward by dx, dy px.
  const r = rng(seed);
  const n = 40;
  const jag = () => 8 + r() * 14;
  const out = [];
  for (let i = 0; i < n; i++) out.push([i / n, 0, 0, -jag()]);
  for (let i = 0; i < n; i++) out.push([1, i / n, jag(), 0]);
  for (let i = 0; i < n; i++) out.push([1 - i / n, 1, 0, jag()]);
  for (let i = 0; i < n; i++) out.push([0, 1 - i / n, -jag(), 0]);
  return out;
}

// ---- the layer ----------------------------------------------------------------------------------------------------

export function createLayer() {
  let world = null;
  let palette = null;
  let regions = [];
  let tex = null; // {key, canvas, glow, rim, style, colours}

  function build(rect, scale) {
    const style = styleFor(world);
    const key = `${style}|${world?.id}|${Math.round(rect.w)}x${Math.round(rect.h)}|${scale}|${JSON.stringify(palette)}`;
    if (tex?.key === key) return tex;
    const w = Math.max(1, Math.round(rect.w * scale));
    const h = Math.max(1, Math.round(rect.h * scale));
    const canvas = makeCanvas(w, h);
    const glow = makeCanvas(w, h);
    const g = canvas.getContext("2d");
    const c = colours(style, palette);
    const seed = hash(world?.id ?? "none");
    TEXTURES[style](g, w, h, c, rng(seed), glow);
    tex = { key, canvas, glow, style, c, rim: makeRim(seed) };
    return tex;
  }

  return {
    update(state) {
      world = state["world.current"]?.world ?? null;
      palette = state.palette ?? null;
      regions = state["world.objects"]?.terrain?.open_regions ?? [];
    },

    draw(ctx, rect, t, beat) {
      const m = ctx.getTransform?.();
      const scale = Math.min(2, Math.max(1, m?.a || 1));
      const tx = build(rect, scale);
      drawEdge(ctx, rect, tx.c, tx.rim, t);
      ctx.save();
      ctx.beginPath();
      ctx.rect(rect.x, rect.y, rect.w, rect.h);
      ctx.clip();
      ctx.drawImage(tx.canvas, rect.x, rect.y, rect.w, rect.h);
      ctx.translate(rect.x, rect.y);
      ANIMATE[tx.style](ctx, rect.w, rect.h, tx.c, t, beat, { glow: tx.glow }, rect.unit ?? 1);
      // open regions: a touch brighter
      for (const reg of regions) {
        const x = (reg.x ?? reg[0]) * rect.w, y = (reg.y ?? reg[1]) * rect.h;
        const w = (reg.w ?? reg[2]) * rect.w, h = (reg.h ?? reg[3]) * rect.h;
        if (![x, y, w, h].every(Number.isFinite)) continue;
        const rg = ctx.createRadialGradient(x + w / 2, y + h / 2, 0, x + w / 2, y + h / 2, Math.max(w, h) * 0.6);
        rg.addColorStop(0, `rgba(255,255,240,${0.08 + 0.04 * beat})`);
        rg.addColorStop(1, "rgba(255,255,240,0)");
        ctx.fillStyle = rg;
        ctx.fillRect(x, y, w, h);
      }
      // inner shadow at the table edge so the rim reads as a drop
      const edge = Math.min(rect.w, rect.h) * 0.05;
      for (const [x0, y0, x1, y1, rx, ry, rw, rh] of [
        [0, 0, 0, edge, 0, 0, rect.w, edge], [0, rect.h, 0, rect.h - edge, 0, rect.h - edge, rect.w, edge],
        [0, 0, edge, 0, 0, 0, edge, rect.h], [rect.w, 0, rect.w - edge, 0, rect.w - edge, 0, edge, rect.h],
      ]) {
        const lg = ctx.createLinearGradient(x0, y0, x1, y1);
        lg.addColorStop(0, "rgba(0,0,0,0.35)");
        lg.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = lg;
        ctx.fillRect(rx, ry, rw, rh);
      }
      ctx.restore();
    },
  };
}
