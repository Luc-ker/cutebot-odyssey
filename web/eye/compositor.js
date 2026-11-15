// Local renderer (docs/local-renderer.md): draws the world's miniatures over the real objects, on the
// laptop, at the camera's frame rate, with no network service in the loop.
//
// Per video frame:
//   1. the camera frame;
//   2. for each object that has a role (scene.js, farthest first):
//        cover   - its segmentation outline, enlarged, is filled with the surrounding colour on a
//                  low-resolution layer that is scaled up (soft edges without a blur filter, which is
//                  slow on integrated GPUs), so the real object doesn't peek out around the sprite;
//        shadow  - a soft contact shadow where it meets the table;
//        sprite  - the role's miniature (sprites.js), sized to cover the object, standing on its bottom
//                  edge, shaded towards the colour and brightness around it;
//        decal   - flat roles (river, road, bridge...) fill the outline with an animated texture instead;
//   3. world particles (motes, snow, embers...);
//   4. the colour grade + grain over everything (grade.js), so camera and sprites share one look.
//
// `createCompositor(doc)` gives {start(stream) -> MediaStream, stop(), scene, setLook, setDebug, pulse};
// the `local` restyle provider (restyler.js) wraps it. Browser only.

import { createScene } from "./scene.js";
import { artFor, kingdomRoleForClass, loadSprites } from "./sprites.js";
import { createGrade } from "./grade.js";
import { lookForPrompt } from "./looks.js";

export const MAX_WIDTH = 960;   // render at most this wide; the display scales up
const COVER = 1.12;             // sprites are drawn this much larger than the object's box
const AMBIENT_EVERY_MS = 200;
const COVER_SCALE = 1 / 8;      // cover layer resolution; lower = softer edges

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** Pure: canvas size for a video of vw x vh, at most `max` wide, even numbers. */
export function renderSize(vw, vh, max = MAX_WIDTH) {
  if (!(vw > 0 && vh > 0)) return [640, 360];
  const w = Math.min(vw, max);
  return [Math.round(w / 2) * 2, Math.round((w * vh) / vw / 2) * 2];
}

/** Pure: where a sprite of sw x sh goes to cover box {x1,y1,x2,y2} (pixels): {x, y, w, h}, base on the box bottom. */
export function spritePlacement(sw, sh, box, cover = COVER) {
  const bw = box.x2 - box.x1, bh = box.y2 - box.y1;
  const scale = Math.max((bw * cover) / sw, (bh * cover) / sh);
  const w = sw * scale, h = sh * scale;
  const cx = (box.x1 + box.x2) / 2;
  const base = box.y2 + bh * 0.04;
  return { x: cx - w / 2, y: base - h, w, h };
}

/** Pure: points scaled by `k` about their centroid. */
export function dilate(points, k) {
  const n = points.length;
  const cx = points.reduce((s, p) => s + p[0], 0) / n, cy = points.reduce((s, p) => s + p[1], 0) / n;
  return points.map(([x, y]) => [cx + (x - cx) * k, cy + (y - cy) * k]);
}

/** Pure: relative luminance 0..1 of an [r,g,b] 0..255 colour. */
export function luminance([r, g, b]) {
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
}

// ---------------------------------------------------------------------------------------------
// Decal textures: small procedural tiles, repeated as patterns.

function tile(doc, size, paint) {
  const c = doc.createElement("canvas");
  c.width = c.height = size;
  paint(c.getContext("2d"), size);
  return c;
}

function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296);
}

function makeDecalTiles(doc) {
  return {
    water: tile(doc, 96, (g, n) => {
      const grad = g.createLinearGradient(0, 0, 0, n);
      grad.addColorStop(0, "#2f7fb6"); grad.addColorStop(1, "#1d5f93");
      g.fillStyle = grad; g.fillRect(0, 0, n, n);
      g.strokeStyle = "rgba(220,245,255,.55)"; g.lineWidth = 2; g.lineCap = "round";
      const r = rng(7);
      for (let i = 0; i < 9; i++) {
        const x = r() * n, y = r() * n, l = 10 + r() * 14;
        g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + l / 2, y - 3, x + l, y); g.stroke();
      }
    }),
    cobble: tile(doc, 96, (g, n) => {
      g.fillStyle = "#6d6257"; g.fillRect(0, 0, n, n);
      const r = rng(3);
      for (let row = 0; row < 6; row++) for (let col = 0; col < 6; col++) {
        const x = col * 16 + (row % 2) * 8 + r() * 3, y = row * 16 + r() * 3;
        const v = 140 + Math.floor(r() * 50);
        g.fillStyle = `rgb(${v},${v - 10},${v - 22})`;
        g.beginPath(); g.ellipse(x % n, y, 7, 6, r(), 0, Math.PI * 2); g.fill();
        g.fillStyle = "rgba(255,255,255,.18)";
        g.beginPath(); g.ellipse(x % n - 2, y - 2, 3, 2, 0, 0, Math.PI * 2); g.fill();
      }
    }),
    planks: tile(doc, 96, (g, n) => {
      for (let i = 0; i < 6; i++) {
        g.fillStyle = i % 2 ? "#8a5a32" : "#9b6a3c";
        g.fillRect(0, i * 16, n, 15);
        g.fillStyle = "#4a2e18"; g.fillRect(0, i * 16 + 15, n, 1);
        g.fillStyle = "rgba(40,24,10,.6)"; g.fillRect((i * 37) % n, i * 16 + 6, 3, 3);
      }
    }),
    ice: tile(doc, 96, (g, n) => {
      const grad = g.createLinearGradient(0, 0, n, n);
      grad.addColorStop(0, "#dff4ff"); grad.addColorStop(1, "#a9d6ef");
      g.fillStyle = grad; g.fillRect(0, 0, n, n);
      g.strokeStyle = "rgba(255,255,255,.8)"; g.lineWidth = 1;
      const r = rng(11);
      for (let i = 0; i < 6; i++) {
        g.beginPath(); let x = r() * n, y = r() * n; g.moveTo(x, y);
        for (let k = 0; k < 3; k++) { x += (r() - 0.5) * 30; y += (r() - 0.5) * 30; g.lineTo(x, y); }
        g.stroke();
      }
    }),
    ash: tile(doc, 96, (g, n) => {
      g.fillStyle = "#3b3533"; g.fillRect(0, 0, n, n);
      const r = rng(5);
      for (let i = 0; i < 160; i++) {
        g.fillStyle = r() < 0.15 ? "rgba(255,120,40,.7)" : `rgba(${90 + r() * 60},${85 + r() * 50},${80 + r() * 40},.6)`;
        g.fillRect(r() * n, r() * n, 1 + r() * 2, 1 + r() * 2);
      }
    }),
  };
}

// ---------------------------------------------------------------------------------------------
// Particles

function makeParticles(look, w, h) {
  const r = rng(42);
  const { kind, count } = look.particles ?? { kind: "none", count: 0 };
  return Array.from({ length: kind === "none" ? 0 : count }, () => ({
    x: r() * w, y: r() * h, z: 0.3 + r() * 0.7, phase: r() * Math.PI * 2, speed: 0.5 + r(),
  }));
}

function drawParticles(ctx, parts, look, w, h, dt, t) {
  const { kind, colour } = look.particles ?? {};
  if (!parts.length) return;
  const [r, g, b] = colour;
  const unit = w / 640;
  ctx.save();
  ctx.globalCompositeOperation = kind === "snow" || kind === "bubbles" ? "source-over" : "lighter";
  for (const p of parts) {
    const s = dt / 1000;
    if (kind === "snow") { p.y += 26 * p.speed * p.z * s * unit; p.x += Math.sin(t / 900 + p.phase) * 10 * s * unit; }
    else if (kind === "embers") { p.y -= 34 * p.speed * p.z * s * unit; p.x += Math.sin(t / 500 + p.phase) * 14 * s * unit; }
    else if (kind === "bubbles") { p.y -= 22 * p.speed * p.z * s * unit; p.x += Math.sin(t / 700 + p.phase) * 8 * s * unit; }
    else { p.x += Math.sin(t / 2600 + p.phase) * 7 * s * unit; p.y += Math.cos(t / 3100 + p.phase) * 5 * s * unit - 2 * s * unit; }
    if (p.y > h + 10) p.y = -10; if (p.y < -10) p.y = h + 10;
    if (p.x > w + 10) p.x = -10; if (p.x < -10) p.x = w + 10;
    const twinkle = kind === "fireflies" ? 0.5 + 0.5 * Math.sin(t / 380 + p.phase * 3) : 0.75 + 0.25 * Math.sin(t / 800 + p.phase);
    const size = (kind === "snow" ? 2.2 : kind === "bubbles" ? 2.6 : 1.6) * p.z * unit;
    ctx.globalAlpha = (kind === "snow" ? 0.85 : 0.6) * p.z * twinkle;
    if (kind === "bubbles") {
      ctx.strokeStyle = `rgb(${r},${g},${b})`; ctx.lineWidth = 0.8 * unit;
      ctx.beginPath(); ctx.arc(p.x, p.y, size * 1.6, 0, Math.PI * 2); ctx.stroke();
    } else {
      const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, size * 3);
      grad.addColorStop(0, `rgba(${r},${g},${b},1)`); grad.addColorStop(1, `rgba(${r},${g},${b},0)`);
      ctx.fillStyle = grad;
      ctx.fillRect(p.x - size * 3, p.y - size * 3, size * 6, size * 6);
    }
  }
  ctx.restore();
}

// ---------------------------------------------------------------------------------------------

export function createCompositor(doc = globalThis.document, opts = {}) {
  const now = opts.now ?? (() => performance.now());
  const scene = opts.scene ?? createScene({ fallbackRole: kingdomRoleForClass });
  const spritesReady = (opts.loadSprites ?? loadSprites)();
  let sprites = null;
  spritesReady.then((s) => { sprites = s; });

  const sceneCanvas = doc.createElement("canvas");
  const ctx = sceneCanvas.getContext("2d");
  const grade = createGrade(doc, { webgl: opts.webgl !== false });
  const tint = doc.createElement("canvas");             // per-sprite shading scratch
  const tctx = tint.getContext("2d");
  const ambient = doc.createElement("canvas");          // tiny copy of the frame, for local colours
  ambient.width = 32; ambient.height = 18;
  const actx = ambient.getContext("2d", { willReadFrequently: true });
  const coverCanvas = doc.createElement("canvas");     // low-res cover shapes, scaled up = soft edges
  const cctx = coverCanvas.getContext("2d");
  const decals = makeDecalTiles(doc);
  const patterns = {};

  let look = lookForPrompt("kingdom");
  let particles = [];
  let debug = false;
  let pulse = 0;
  let video = null, output = null, running = false, handle = null, generation = 0;
  let ambientData = null, ambientAt = -Infinity, lastT = null;
  const frameListeners = new Set();

  function ambientAround(box, W, H) {
    if (!ambientData) return [128, 128, 128];
    const gx = (x) => clamp(Math.floor((x / W) * 32), 0, 31), gy = (y) => clamp(Math.floor((y / H) * 18), 0, 17);
    const bw = box.x2 - box.x1, bh = box.y2 - box.y1;
    const ox1 = gx(box.x1 - bw * 0.4), ox2 = gx(box.x2 + bw * 0.4), oy1 = gy(box.y1 - bh * 0.2), oy2 = gy(box.y2 + bh * 0.3);
    const ix1 = gx(box.x1), ix2 = gx(box.x2), iy1 = gy(box.y1), iy2 = gy(box.y2);
    let r = 0, g = 0, b = 0, n = 0;
    for (let y = oy1; y <= oy2; y++) for (let x = ox1; x <= ox2; x++) {
      if (x >= ix1 && x <= ix2 && y >= iy1 && y <= iy2 && ox2 - ox1 > ix2 - ix1) continue; // the ring only
      const i = (y * 32 + x) * 4;
      r += ambientData[i]; g += ambientData[i + 1]; b += ambientData[i + 2]; n++;
    }
    return n ? [r / n, g / n, b / n] : [128, 128, 128];
  }

  function polygon(points, g = ctx, k = 1) {
    g.beginPath();
    points.forEach(([x, y], i) => (i ? g.lineTo(x * k, y * k) : g.moveTo(x * k, y * k)));
    g.closePath();
  }

  /** All sprites' cover shapes in one low-res pass, then one scaled-up draw. */
  function drawCovers(items, W, H) {
    const cw = Math.max(8, Math.round(W * COVER_SCALE)), ch = Math.max(8, Math.round(H * COVER_SCALE));
    if (coverCanvas.width !== cw || coverCanvas.height !== ch) { coverCanvas.width = cw; coverCanvas.height = ch; }
    cctx.clearRect(0, 0, cw, ch);
    let any = false;
    for (const item of items) {
      if (artFor(item.role, item.behaviour).kind !== "sprite") continue;
      const px = { x1: item.box.x1 * W, y1: item.box.y1 * H, x2: item.box.x2 * W, y2: item.box.y2 * H };
      if (px.x2 - px.x1 < 4 || px.y2 - px.y1 < 4) continue;
      cctx.globalAlpha = 0.95 * item.alpha;
      cctx.fillStyle = `rgb(${ambientAround(px, W, H).map(Math.round).join(",")})`;
      polygon(shapeFor(item, px, 1.22), cctx, COVER_SCALE); // generous: narrow sprites leave the sides open
      cctx.fill();
      any = true;
    }
    if (!any) return;
    ctx.save();
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(coverCanvas, 0, 0, W, H);
    ctx.restore();
  }

  function shapeFor(item, px, k) {
    const { x1, y1, x2, y2 } = px;
    if (item.outline) {
      return dilate(item.outline.map(([u, v]) => [x1 + u * (x2 - x1), y1 + v * (y2 - y1)]), k);
    }
    // No outline (detection-only model): an ellipse inside the box.
    const cx = (x1 + x2) / 2, cy = (y1 + y2) / 2, rx = ((x2 - x1) / 2) * k, ry = ((y2 - y1) / 2) * k;
    return Array.from({ length: 20 }, (_, i) => [cx + rx * Math.cos((i / 20) * Math.PI * 2), cy + ry * Math.sin((i / 20) * Math.PI * 2)]);
  }

  function drawItem(item, W, H, t) {
    const px = { x1: item.box.x1 * W, y1: item.box.y1 * H, x2: item.box.x2 * W, y2: item.box.y2 * H };
    const bw = px.x2 - px.x1, bh = px.y2 - px.y1;
    if (bw < 4 || bh < 4) return;
    const art = artFor(item.role, item.behaviour);
    const amb = ambientAround(px, W, H);
    const lum = luminance(amb);
    const alpha = item.alpha;
    ctx.save();

    if (art.kind === "decal") {
      const shape = shapeFor(item, px, 1.06);
      const pat = (patterns[art.key] ??= ctx.createPattern(decals[art.key], "repeat"));
      if (art.key === "water" && pat?.setTransform && globalThis.DOMMatrix) {
        pat.setTransform(new DOMMatrix().translateSelf((t / 60) % 96, Math.sin(t / 900) * 4).scaleSelf(W / 640));
      } else if (pat?.setTransform && globalThis.DOMMatrix) {
        pat.setTransform(new DOMMatrix().scaleSelf(W / 640));
      }
      ctx.globalAlpha = 0.92 * alpha;
      polygon(shape);
      ctx.fillStyle = pat;
      ctx.fill();
      // soft darker rim so the patch sits in the table instead of on it
      ctx.globalAlpha = 0.3 * alpha;
      ctx.strokeStyle = "rgba(20,14,8,.8)";
      ctx.lineWidth = Math.max(2, bw * 0.035);
      ctx.stroke();
      ctx.restore();
      return;
    }

    const sprite = sprites?.get(art.key);
    if (!sprite) { ctx.restore(); return; }

    // 1. (the cover was drawn for all items by drawCovers) 2. contact shadow
    const grow = 0.85 + 0.15 * item.appear;
    const place = spritePlacement(sprite.width, sprite.height, px);
    const cx = (px.x1 + px.x2) / 2, base = place.y + place.h;
    const rx = place.w * 0.5 * grow, ry = Math.max(3, place.w * 0.1);
    ctx.globalAlpha = 0.5 * alpha;
    ctx.translate(cx, base - ry * 0.3);
    ctx.scale(1, ry / rx);
    const sh = ctx.createRadialGradient(0, 0, 0, 0, 0, rx);
    sh.addColorStop(0, "rgba(10,6,2,.85)"); sh.addColorStop(0.6, "rgba(10,6,2,.35)"); sh.addColorStop(1, "rgba(10,6,2,0)");
    ctx.fillStyle = sh;
    ctx.fillRect(-rx, -rx, rx * 2, rx * 2);
    ctx.setTransform(1, 0, 0, 1, 0, 0);

    // 3. the sprite, shaded towards its surroundings
    const dw = Math.max(1, Math.round(place.w * grow)), dh = Math.max(1, Math.round(place.h * grow));
    const bob = item.behaviour === "threat" ? Math.sin(t / 320 + item.seed * 6.28) * dh * 0.012 : 0;
    if (tint.width < dw || tint.height < dh) { tint.width = Math.max(tint.width, dw); tint.height = Math.max(tint.height, dh); }
    tctx.clearRect(0, 0, dw, dh);
    tctx.globalCompositeOperation = "source-over";
    tctx.globalAlpha = 1;
    tctx.drawImage(sprite, 0, 0, dw, dh);
    tctx.globalCompositeOperation = "source-atop";
    tctx.globalAlpha = 0.16;
    tctx.fillStyle = `rgb(${amb.map(Math.round).join(",")})`;
    tctx.fillRect(0, 0, dw, dh);
    if (lum < 0.42) { tctx.globalAlpha = clamp((0.42 - lum) * 1.1, 0, 0.45); tctx.fillStyle = "#000"; tctx.fillRect(0, 0, dw, dh); }
    else if (lum > 0.65) { tctx.globalAlpha = clamp((lum - 0.65) * 0.6, 0, 0.15); tctx.fillStyle = "#fff"; tctx.fillRect(0, 0, dw, dh); }
    tctx.globalCompositeOperation = "source-over";

    ctx.globalAlpha = alpha;
    ctx.drawImage(tint, 0, 0, dw, dh, cx - dw / 2, base - dh + bob, dw, dh);
    ctx.restore();
  }

  function drawDebug(items, W, H) {
    ctx.save();
    ctx.font = `${Math.round(12 * W / 640)}px system-ui, sans-serif`;
    for (const it of items) {
      const x1 = it.box.x1 * W, y1 = it.box.y1 * H, w = (it.box.x2 - it.box.x1) * W, h = (it.box.y2 - it.box.y1) * H;
      ctx.strokeStyle = "#0f0"; ctx.lineWidth = 1.5; ctx.strokeRect(x1, y1, w, h);
      if (it.outline) {
        ctx.strokeStyle = "#ff0";
        ctx.beginPath();
        it.outline.forEach(([u, v], i) => (i ? ctx.lineTo(x1 + u * w, y1 + v * h) : ctx.moveTo(x1 + u * w, y1 + v * h)));
        ctx.closePath(); ctx.stroke();
      }
      ctx.fillStyle = "#0f0";
      ctx.fillText(`${it.id} ${it.cls} -> ${it.role}`, x1, Math.max(12, y1 - 4));
    }
    const lat = scene.latencyMs;
    ctx.fillStyle = "#0f0";
    ctx.fillText(`vision age ${lat === null ? "?" : Math.round(lat) + " ms"} · grade ${grade.kind}`, 8, H - 8);
    ctx.restore();
  }

  function frame() {
    if (!running) return;
    const vw = video.videoWidth, vh = video.videoHeight;
    if (vw && vh && video.currentTime !== frame.last) {
      frame.last = video.currentTime;
      const t = now();
      const dt = lastT === null ? 16 : clamp(t - lastT, 0, 100);
      lastT = t;
      const [W, H] = renderSize(vw, vh);
      if (sceneCanvas.width !== W || sceneCanvas.height !== H) {
        sceneCanvas.width = W; sceneCanvas.height = H;
        particles = makeParticles(look, W, H);
      }
      ctx.drawImage(video, 0, 0, W, H);
      if (t - ambientAt > AMBIENT_EVERY_MS) {
        ambientAt = t;
        actx.drawImage(video, 0, 0, 32, 18);
        ambientData = actx.getImageData(0, 0, 32, 18).data;
      }
      const items = scene.items(t);
      drawCovers(items, W, H);
      for (const it of items) drawItem(it, W, H, t);
      drawParticles(ctx, particles, look, W, H, dt, t);
      if (debug) drawDebug(items, W, H);
      grade.render(sceneCanvas, look, t, pulse);
      pulse *= 0.86;
      frameListeners.forEach((cb) => cb());
    }
    schedule();
  }
  frame.last = -1;

  function schedule() {
    if (!running) return;
    handle = video.requestVideoFrameCallback
      ? { vfc: video.requestVideoFrameCallback(frame) }
      : { raf: requestAnimationFrame(frame) };
  }

  return {
    scene,
    spritesReady,
    get canvas() { return grade.canvas; },
    get gradeKind() { return grade.kind; },
    /** Start drawing `stream`; resolves with the composited MediaStream. */
    async start(stream, fps = 30) {
      const own = ++generation;
      await spritesReady;
      video = Object.assign(doc.createElement("video"), { muted: true, playsInline: true, srcObject: stream });
      await video.play().catch(() => {});
      if (own !== generation) throw new Error("Renderer stopped");
      const [W, H] = renderSize(video.videoWidth, video.videoHeight);
      grade.canvas.width = W; grade.canvas.height = H;
      running = true;
      lastT = null;
      schedule();
      output = grade.canvas.captureStream(fps);
      return output;
    },
    stop() {
      generation++;
      running = false;
      if (handle?.raf) cancelAnimationFrame(handle.raf);
      if (handle?.vfc && video?.cancelVideoFrameCallback) video.cancelVideoFrameCallback(handle.vfc);
      handle = null;
      if (video) video.srcObject = null;
      output?.getTracks().forEach((tr) => tr.stop());
      output = null;
    },
    setLook(next) {
      look = next;
      particles = makeParticles(look, sceneCanvas.width || 640, sceneCanvas.height || 360);
    },
    get look() { return look; },
    setDebug(on) { debug = Boolean(on); },
    get debug() { return debug; },
    beat(strength = 1) { pulse = Math.max(pulse, clamp(strength, 0, 1)); },
    onFrame(cb) { frameListeners.add(cb); return () => frameListeners.delete(cb); },
  };
}
