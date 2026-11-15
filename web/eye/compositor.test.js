// node --test web/eye/compositor.test.js  (pure helpers; the drawing itself is checked in web/eye/preview.html)
import { test } from "node:test";
import assert from "node:assert/strict";
import { dilate, luminance, renderSize, spritePlacement } from "./compositor.js";
import { filterFor } from "./grade.js";

test("renderSize caps the width and keeps the aspect", () => {
  assert.deepEqual(renderSize(1920, 1080), [960, 540]);
  assert.deepEqual(renderSize(640, 480), [640, 480]);
  assert.deepEqual(renderSize(0, 0), [640, 360]);
});

test("a sprite covers its box and stands on the box bottom", () => {
  const box = { x1: 100, y1: 50, x2: 160, y2: 200 };       // tall bottle
  const p = spritePlacement(110, 280, box);                   // tower sprite
  assert.ok(p.w >= 60 && p.h >= 150, "covers the box");
  assert.ok(Math.abs(p.x + p.w / 2 - 130) < 1e-9, "centred");
  assert.ok(Math.abs(p.y + p.h - (200 + 150 * 0.04)) < 1e-9, "base just below the box bottom");
  const wide = spritePlacement(110, 280, { x1: 0, y1: 0, x2: 200, y2: 40 }); // flat keyboard, tall sprite
  assert.ok(wide.w >= 200, "a narrow sprite still covers a wide box");
});

test("dilate grows a shape about its centroid", () => {
  assert.deepEqual(dilate([[0, 0], [2, 0], [2, 2], [0, 2]], 2), [[-1, -1], [3, -1], [3, 3], [-1, 3]]);
});

test("luminance and grade fallback filter", () => {
  assert.ok(Math.abs(luminance([255, 255, 255]) - 1) < 1e-9);
  assert.equal(luminance([0, 0, 0]), 0);
  assert.equal(filterFor({ saturation: 1.2, contrast: 1.1, brightness: 1 }), "saturate(1.200) contrast(1.100) brightness(1.000)");
});
