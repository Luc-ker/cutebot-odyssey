// Local renderer preview (docs/local-renderer.md): see and tune the sprites without the robot, the phone,
// the hub or the vision service.
//
// A synthetic "table" video (wood, a bottle, a cup, a book, a keyboard, a backpack) pans left and right as if
// the robot were turning. Fake `vision.state` messages describe those objects with outlines, delayed by
// 150 ms like the real pipeline, and Kingdom roles come from the stable-mode class table. Add ?camera to
// use this laptop's webcam instead (no objects are detected then: the vision service isn't running).
// Add ?gallery to see one object of every model archetype side by side on a still camera.

import { createCompositor } from "./compositor.js";
import { LOOKS } from "./looks.js";
import { kingdomRoleForClass } from "./sprites.js";

const $ = (id) => document.getElementById(id);
const W = 1280, H = 720;
const VISION_HZ = 10, VISION_DELAY_MS = 150;

// Objects in "table" coordinates (pixels on a 1.6x wide table); the camera pans across.
const GALLERY = new URLSearchParams(location.search).has("gallery");
// One role per model archetype, laid out in two rows.
const GALLERY_ROLES = ["castle", "palace", "fortress", "temple", "watchtower", "beacon", "village", "forest",
  "dragon", "wolf_pack", "treasure", "den", "crystal", "ship", "mountain", "thing"];
const GALLERY_OBJECTS = GALLERY_ROLES.map((role, i) => ({
  id: 100 + i, cls: role, role, x: 120 + (i % 8) * 148 + (Math.floor(i / 8) ? 60 : 0), y: Math.floor(i / 8) ? 690 : 470,
  w: 110, h: 120, colour: "#777", shape: "box",
}));
const TABLE_OBJECTS = [
  { id: 1, cls: "bottle", x: 520, y: 520, w: 70, h: 230, colour: "#2f8f5a", shape: "bottle" },
  { id: 2, cls: "cup", x: 860, y: 590, w: 110, h: 120, colour: "#e8e2d6", shape: "cup" },
  { id: 3, cls: "book", x: 1180, y: 620, w: 230, h: 90, colour: "#a3312b", shape: "box" },
  { id: 4, cls: "keyboard", x: 260, y: 660, w: 300, h: 50, colour: "#33343a", shape: "box" },
  { id: 5, cls: "backpack", x: 1560, y: 520, w: 220, h: 260, colour: "#3d5a8a", shape: "bag" },
];
const OBJECTS = GALLERY ? GALLERY_OBJECTS : TABLE_OBJECTS;

function shapePoints(o) {
  const { x, y, w, h } = o;
  if (o.shape === "bottle") {
    return [[x - w * 0.15, y - h], [x + w * 0.15, y - h], [x + w * 0.15, y - h * 0.7], [x + w / 2, y - h * 0.55],
      [x + w / 2, y], [x - w / 2, y], [x - w / 2, y - h * 0.55], [x - w * 0.15, y - h * 0.7]];
  }
  if (o.shape === "cup") {
    return [[x - w / 2, y - h], [x + w * 0.3, y - h], [x + w * 0.3, y - h * 0.75], [x + w / 2, y - h * 0.7],
      [x + w / 2, y - h * 0.35], [x + w * 0.3, y - h * 0.3], [x + w * 0.25, y], [x - w * 0.45, y]];
  }
  if (o.shape === "bag") {
    return [[x - w * 0.35, y - h], [x + w * 0.35, y - h], [x + w / 2, y - h * 0.8], [x + w / 2, y], [x - w / 2, y], [x - w / 2, y - h * 0.8]];
  }
  return [[x - w / 2, y - h], [x + w / 2, y - h], [x + w / 2, y], [x - w / 2, y]];
}

function panAt(t) {
  if (GALLERY) return 0;
  return 320 + Math.sin(t / 2600) * 320 + Math.sin(t / 900) * 18; // slow turn plus a little wobble
}

function drawTable(ctx, t) {
  const pan = panAt(t);
  const horizon = H * 0.42;
  // wall
  const wall = ctx.createLinearGradient(0, 0, 0, horizon);
  wall.addColorStop(0, "#cfc8bd"); wall.addColorStop(1, "#b1a89a");
  ctx.fillStyle = wall; ctx.fillRect(0, 0, W, horizon);
  // table top with grain
  const top = ctx.createLinearGradient(0, horizon, 0, H);
  top.addColorStop(0, "#9c7650"); top.addColorStop(1, "#c39a6b");
  ctx.fillStyle = top; ctx.fillRect(0, horizon, W, H - horizon);
  ctx.strokeStyle = "rgba(70,45,20,.18)"; ctx.lineWidth = 2;
  for (let i = 0; i < 14; i++) {
    const y = horizon + (i / 14) ** 1.6 * (H - horizon);
    ctx.beginPath(); ctx.moveTo(0, y); ctx.bezierCurveTo(W * 0.3, y + 6, W * 0.7, y - 6, W, y + 3); ctx.stroke();
  }
  for (const o of OBJECTS) {
    const pts = shapePoints(o).map(([x, y]) => [x - pan, y]);
    ctx.fillStyle = "rgba(0,0,0,.25)";
    ctx.beginPath(); ctx.ellipse(o.x - pan, o.y, o.w * 0.55, o.w * 0.12, 0, 0, Math.PI * 2); ctx.fill();
    const g = ctx.createLinearGradient(o.x - pan - o.w / 2, 0, o.x - pan + o.w / 2, 0);
    g.addColorStop(0, o.colour); g.addColorStop(1, "#111");
    ctx.fillStyle = g;
    ctx.beginPath(); pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.closePath(); ctx.fill();
  }
}

function visionStateAt(t) {
  const pan = panAt(t);
  const objects = [];
  for (const o of OBJECTS) {
    const pts = shapePoints(o).map(([x, y]) => [x - pan, y]);
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const x1 = Math.max(0, Math.min(...xs)), x2 = Math.min(W, Math.max(...xs));
    const y1 = Math.max(0, Math.min(...ys)), y2 = Math.min(H, Math.max(...ys));
    if (x2 - x1 < 10) continue; // out of view
    const jitter = () => (Math.random() - 0.5) * 4; // detector boxes wobble a few pixels
    objects.push({
      id: o.id, cls: o.cls, conf: 0.9,
      pos: [((x1 + x2) / 2 + jitter()) / W, ((y1 + y2) / 2 + jitter()) / H],
      size: [(x2 - x1 + jitter()) / W, (y2 - y1 + jitter()) / H],
      outline: pts.map(([x, y]) => [Math.min(1, Math.max(0, x / W)), Math.min(1, Math.max(0, y / H))]),
    });
  }
  return { frame_ts: t / 1000, client_ts: t, objects, giants: [] };
}

async function cameraStream() {
  return navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: false });
}

// Each synthetic frame carries its own scene time as 16 black/white blocks in the bottom-left corner.
// Fake vision reads that code back from the frame the page is actually showing, exactly as the real
// vision service only ever sees frames the eye page grabbed, so video lag can't pull the two apart.
const CODE_BITS = 16, CODE_PX = 6;

function drawCode(ctx, t) {
  const v = Math.round(t / 10) & 0xffff;
  for (let i = 0; i < CODE_BITS; i++) {
    ctx.fillStyle = (v >> i) & 1 ? "#fff" : "#000";
    ctx.fillRect(i * CODE_PX, H - CODE_PX, CODE_PX, CODE_PX);
  }
}

/** Scene time (ms) of the frame `video` shows now, or null. */
function readCode(video, probe) {
  if (video.readyState < 2) return null;
  const g = probe.getContext("2d", { willReadFrequently: true });
  g.drawImage(video, 0, video.videoHeight - CODE_PX, CODE_BITS * CODE_PX, CODE_PX, 0, 0, CODE_BITS * CODE_PX, CODE_PX);
  const px = g.getImageData(0, 0, CODE_BITS * CODE_PX, CODE_PX).data;
  let v = 0;
  for (let i = 0; i < CODE_BITS; i++) if (px[((CODE_PX >> 1) * CODE_BITS * CODE_PX + i * CODE_PX + (CODE_PX >> 1)) * 4] > 127) v |= 1 << i;
  // Unwrap against the clock: the frame is at most a few seconds old.
  const now = performance.now();
  const base = Math.round(now / 10) & ~0xffff;
  let t = (base | v) * 10;
  if (t > now + 1000) t -= 0x10000 * 10;
  return t;
}

function syntheticStream() {
  const c = Object.assign(document.createElement("canvas"), { width: W, height: H });
  const ctx = c.getContext("2d");
  const loop = () => { const t = performance.now(); drawTable(ctx, t); drawCode(ctx, t); requestAnimationFrame(loop); };
  loop();
  return c.captureStream(30);
}

async function main() {
  const params = new URLSearchParams(location.search);
  const useCamera = params.has("camera");
  const stream = useCamera ? await cameraStream() : syntheticStream();
  $("raw").srcObject = stream;

  const compositor = createCompositor(document);
  globalThis.compositor = compositor; // for poking at from the console
  const scene = compositor.scene;
  if (!useCamera) {
    // Fake the vision service: 10 times a second, "grab" the frame being shown (like frames.js), describe
    // the scene at that frame's own time, and deliver the state 150 ms later stamped with the grab time.
    const probe = Object.assign(document.createElement("canvas"), { width: CODE_BITS * CODE_PX, height: CODE_PX });
    setInterval(() => {
      const grabbed = performance.now();
      const sceneTime = readCode($("raw"), probe);
      if (sceneTime === null) return;
      const state = { ...visionStateAt(sceneTime), client_ts: grabbed };
      setTimeout(() => scene.onVision(state, performance.now()), VISION_DELAY_MS);
    }, 1000 / VISION_HZ);
    // Roles as the brain assigns them in stable Kingdom mode, after a short settle.
    setTimeout(() => setInterval(() => scene.onObjects({
      objects: OBJECTS.map((o) => ({ id: o.id, cls: o.cls, ...(o.role ? { role: o.role, behaviour: null } : kingdomRoleForClass(o.cls)), name: null })),
    }, performance.now()), 100), 1200);
  }

  const out = await compositor.start(stream);
  $("styled").srcObject = out;
  $("status").textContent = `grade: ${compositor.gradeKind} · ${useCamera ? "webcam" : "synthetic table"}`;

  const world = $("world");
  for (const key of Object.keys(LOOKS)) world.append(new Option(key, key));
  world.onchange = () => compositor.setLook({ ...compositor.look, ...LOOKS[world.value] });
  $("debug").onchange = (e) => compositor.setDebug(e.target.checked);
  $("split").onchange = (e) => document.body.classList.toggle("split", e.target.checked);

  let frames = 0;
  compositor.onFrame(() => frames++);
  setInterval(() => { $("fps").textContent = `${frames} fps`; frames = 0; }, 1000);
}

main().catch((e) => { $("status").textContent = `Preview failed: ${e.message}`; console.error(e); });
