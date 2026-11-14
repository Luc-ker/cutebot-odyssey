import test from "node:test";
import assert from "node:assert/strict";
import { toScreen, fromScreen, dist, angleTo, bearing } from "./geometry.js";

const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

test("toScreen maps the view onto a rect, honouring its offset", () => {
  assert.deepEqual(toScreen([0, 0], { width: 640, height: 360 }), [0, 0]);
  assert.deepEqual(toScreen([0.5, 0.5], { x: 10, y: 20, width: 640, height: 360 }), [330, 200]);
});

test("fromScreen inverts toScreen", () => {
  const rect = { x: 5, y: 7, width: 640, height: 480 };
  const p = fromScreen(toScreen([0.25, 0.75], rect), rect);
  close(p[0], 0.25);
  close(p[1], 0.75);
});

test("dist and angleTo", () => {
  close(dist([0, 0], [0.3, 0.4]), 0.5);
  close(angleTo([0.5, 0.5], [0.5, 0.6]), Math.PI / 2);
  close(angleTo([0.5, 0.5], [0.6, 0.5]), 0);
});

test("bearing: centre is straight ahead, edges are half the field of view", () => {
  close(bearing(0.5, 60), 0);
  close(bearing(1, 60), Math.PI / 6);
  close(bearing(0, 60), -Math.PI / 6);
});
