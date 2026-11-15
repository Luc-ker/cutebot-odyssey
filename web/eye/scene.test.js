// node --test web/eye/scene.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { APPEAR_MS, FADE_OUT_MS, HOLD_MS, createScene, oneEuro, outlineToBox } from "./scene.js";

const cup = (x, extra = {}) => ({ id: 7, cls: "cup", pos: [x, 0.5], size: [0.1, 0.2], conf: 0.9, ...extra });
const roles = (role = "beacon") => ({ objects: [{ id: 7, cls: "cup", role, behaviour: "friendly", name: "The Lamp" }] });

test("oneEuro passes the first value and smooths jitter", () => {
  const f = oneEuro();
  assert.equal(f.filter(1, 0), 1);
  const out = [0, 1, 0, 1, 0, 1].map((v, i) => f.filter(0.5 + (v - 0.5) * 0.02, (i + 1) * 33));
  for (const v of out) assert.ok(Math.abs(v - 0.5) < 0.6); // never further than the raw jitter
  assert.ok(Math.abs(out.at(-1) - out.at(-2)) < 0.02);
});

test("outlineToBox makes points relative to the box", () => {
  const rel = outlineToBox([[0.2, 0.4], [0.3, 0.4], [0.3, 0.6]], { x1: 0.2, y1: 0.4, x2: 0.3, y2: 0.6 });
  assert.deepEqual(rel.map((p) => p.map((v) => Math.round(v * 1000) / 1000)), [[0, 0], [1, 0], [1, 1]]);
  assert.equal(outlineToBox([[0, 0]], { x1: 0, y1: 0, x2: 1, y2: 1 }), null);
});

test("an object is drawn only once it has a role, then grows in", () => {
  const s = createScene();
  s.onVision({ objects: [cup(0.5)] }, 1000);
  s.onObjects({ objects: [{ id: 7, cls: "cup", role: null }] }, 1000);
  assert.deepEqual(s.items(1010), []);
  s.onObjects(roles(), 1020);
  const [first] = s.items(1030);
  assert.equal(first.role, "beacon");
  assert.ok(first.alpha < 0.2, "just appeared");
  s.onVision({ objects: [cup(0.5)] }, 1030 + APPEAR_MS - 50); // still in view
  const [later] = s.items(1030 + APPEAR_MS);
  assert.equal(later.alpha, 1);
  assert.ok(Math.abs((later.box.x1 + later.box.x2) / 2 - 0.5) < 1e-6);
});

test("client_ts measures the vision age and motion is predicted to now", () => {
  const s = createScene();
  s.onObjects(roles(), 0);
  // Moving right by 0.1 per 100 ms, each state arriving 150 ms after its frame was grabbed.
  for (let i = 0; i < 6; i++) s.onVision({ client_ts: i * 100, objects: [cup(0.2 + i * 0.1)] }, i * 100 + 150);
  assert.ok(Math.abs(s.latencyMs - 150) < 1);
  let x;
  for (let t = 600; t <= 660; t += 15) { const [it] = s.items(t); x = (it.box.x1 + it.box.x2) / 2; }
  // Last measurement 0.7 at t=500; by t=660 it should be near 0.86, and certainly ahead of 0.7.
  assert.ok(x > 0.78, `predicted ${x}`);
});

test("an object that leaves is held, then fades out, then dropped", () => {
  const s = createScene();
  s.onObjects(roles(), 0);
  s.onVision({ objects: [cup(0.5)] }, 0);
  s.items(0); // role appears
  s.onVision({ objects: [cup(0.5)] }, APPEAR_MS);
  const last = APPEAR_MS; // last time vision reported it
  s.onVision({ objects: [] }, last + 100);
  assert.equal(s.items(last + HOLD_MS - 10)[0].alpha, 1);
  const fading = s.items(last + HOLD_MS + FADE_OUT_MS / 2)[0].alpha;
  assert.ok(fading > 0 && fading < 1);
  assert.deepEqual(s.items(last + HOLD_MS + FADE_OUT_MS + 10), []);
});

test("without world.objects the fallback role is used", () => {
  const s = createScene({ fallbackRole: (cls) => (cls === "cup" ? { role: "beacon", behaviour: "friendly" } : null) });
  s.onVision({ objects: [cup(0.5), { id: 8, cls: "spoon", pos: [0.2, 0.5], size: [0.1, 0.1] }] }, 0);
  assert.deepEqual(s.items(10).map((i) => i.role), ["beacon"]);
});

test("outlines follow the box and the far object is drawn first", () => {
  const s = createScene({ fallbackRole: () => ({ role: "castle" }) });
  const near = { id: 1, cls: "book", pos: [0.3, 0.8], size: [0.2, 0.2], outline: [[0.2, 0.7], [0.4, 0.7], [0.4, 0.9]] };
  const far = { id: 2, cls: "cup", pos: [0.6, 0.3], size: [0.1, 0.1] };
  s.onVision({ objects: [near, far] }, 0);
  const items = s.items(10);
  assert.deepEqual(items.map((i) => i.id), [2, 1]);
  assert.deepEqual(items[1].outline.map((p) => p.map((v) => Math.round(v * 100) / 100 + 0)), [[0, 0], [1, 0], [1, 1]]);
  assert.equal(items[0].outline, null);
});
