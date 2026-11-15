// Local renderer preview (docs/local-renderer.md): see and tune the sprites without the robot, the phone,
// the hub or the vision service.
//
// A synthetic "table" video (wood, a bottle, a cup, a book, a keyboard, a backpack) pans left and right as if
// the robot were turning. Fake `vision.state` messages describe those objects with outlines, delayed by
// 150 ms like the real pipeline, and Kingdom roles come from the stable-mode class table. Add ?camera to
// use this laptop's webcam instead (no objects are detected then: the vision service isn't running).

import { createCompositor } from "./compositor.js";
import { LOOKS } from "./looks.js";
import { kingdomRoleForClass } from "./sprites.js";

const $ = (id) => document.getElementById(id);
const W = 1280, H = 720;
const VISION_HZ = 10, VISION_DELAY_MS = 150;

// Objects in "table" coordinates (pixels on a 1.6x wide table); the camera pans across.
const OBJECTS = [
  { id: 1, cls: "bottle", x: 520, y: 520, w: 70, h: 230, colour: "#2f8f5a", shape: "bottle" },
  { id: 2, cls: "cup", x: 860, y: 590, w: 110, h: 120, colour: "#e8e2d6", shape: "cup" },
  { id: 3, cls: "book", x: 1180, y: 620, w: 230, h: 90, colour: "#a3312b", shape: "box" },
  { id: 4, cls: "keyboard", x: 260, y: 660, w: 300, h: 50, colour: "#33343a", shape: "box" },
  { id: 5, cls: "backpack", x: 1560, y: 520, w: 220, h: 260, colour: "#3d5a8a", shape: "bag" },
];

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

// Time of the scene in the last drawn synthetic frame. Fake vision describes *that* frame, like the real
// vision service describes the frames it is sent, so a throttled tab doesn't pull the two apart.
let drawnAt = 0;

function syntheticStream() {
  const c = Object.assign(document.createElement("canvas"), { width: W, height: H });
  const ctx = c.getContext("2d");
  const loop = () => { drawnAt = performance.now(); drawTable(ctx, drawnAt); requestAnimationFrame(loop); };
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
    // Fake the vision service: a state 10 times a second, each describing a frame 150 ms old.
    setInterval(() => {
      const state = visionStateAt(drawnAt);
      setTimeout(() => scene.onVision(state, performance.now()), VISION_DELAY_MS);
    }, 1000 / VISION_HZ);
    // Roles as the brain assigns them in stable Kingdom mode, after a short settle.
    setTimeout(() => setInterval(() => scene.onObjects({
      objects: OBJECTS.map((o) => ({ id: o.id, cls: o.cls, ...kingdomRoleForClass(o.cls), name: null })),
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
