import test from "node:test";
import assert from "node:assert/strict";
import { toScreen, fromScreen, fitRect, dist, angleTo, setTableSize, getTableAspect } from "./geometry.js";

const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

test("toScreen keeps a 2:1 table centred in a square rect", () => {
  const rect = { x: 0, y: 0, width: 400, height: 400 };
  assert.deepEqual(fitRect(rect, 2), { x: 0, y: 100, width: 400, height: 200 });
  assert.deepEqual(toScreen([0, 0], rect, 2), [0, 100]);
  assert.deepEqual(toScreen([1, 1], rect, 2), [400, 300]);
  assert.deepEqual(toScreen([0.5, 0.5], rect, 2), [200, 200]);
});

test("pillarboxes a tall rect and honours rect offset", () => {
  const rect = { x: 10, y: 20, width: 100, height: 400 };
  assert.deepEqual(toScreen([0, 0], rect, 0.5), [10, 120]);
  assert.deepEqual(toScreen([1, 1], rect, 0.5), [110, 320]);
  const wide = { x: 0, y: 0, width: 1000, height: 100 };
  assert.deepEqual(toScreen([0, 0], wide, 2), [400, 0]);
});

test("fromScreen inverts toScreen", () => {
  const rect = { width: 640, height: 480 };
  const p = fromScreen(toScreen([0.25, 0.75], rect, 2), rect, 2);
  close(p[0], 0.25);
  close(p[1], 0.75);
});

test("table aspect comes from setTableSize", () => {
  setTableSize(120, 80);
  close(getTableAspect(), 1.5);
  setTableSize(200, 100);
  assert.deepEqual(toScreen([1, 1], { width: 400, height: 400 }), [400, 300]);
  setTableSize(120, 80);
});

test("dist and angleTo", () => {
  close(dist([0, 0], [0.3, 0.4]), 0.5);
  close(angleTo([0.5, 0.5], [0.5, 0.6]), Math.PI / 2);
  close(angleTo([0.5, 0.5], [0.6, 0.5]), 0);
});
