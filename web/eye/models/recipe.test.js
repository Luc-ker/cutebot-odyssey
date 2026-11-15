// node --test web/eye/models/recipe.test.js  (the three.js building itself is checked in preview.html?gallery)
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { GENERATOR_KEYS, MAX_EXPANDED, expandParts, normaliseRecipe, proceduralRecipe } from "./recipe.js";
import { SPRITE_KEYS } from "../sprites.js";
import { MAX_WIDEN, fitScale, yawFor } from "./stage3d.js";

const schema = JSON.parse(readFileSync(fileURLToPath(new URL("../../../shared/schemas/model.schema.json", import.meta.url)), "utf8"));
const partProps = schema.properties.parts.items.properties;

test("the JS lists match the shared schema", async () => {
  const { SHAPES, MATERIALS, PART_ANIMS, MODEL_ANIMS } = await import("./recipe.js");
  assert.deepEqual([...SHAPES].sort(), [...partProps.shape.enum].sort());
  assert.deepEqual([...MATERIALS].sort(), [...partProps.material.enum].sort());
  assert.deepEqual([...PART_ANIMS].sort(), [...partProps.anim.enum].sort());
  assert.deepEqual([...MODEL_ANIMS].sort(), [...schema.properties.animation.enum].sort());
});

test("normaliseRecipe clamps and drops like the Python guard", () => {
  const r = normaliseRecipe({ name: "  a\n tower ", animation: "dance", parts: [
    { shape: "box", size: [5, -1, "x"], pos: [3, -2, 0.1], colour: "#ABCDEF", material: "plasma", rot: [400, 0, 0], anim: "none" },
    { shape: "teapot", size: [0.1, 0.1, 0.1], pos: [0, 0, 0], colour: "#ffffff", material: "stone" },
    { shape: "cone", size: [0.1, 0.1, 0.1], pos: [0, 0, 0], colour: "red", material: "stone" },
    { shape: "sphere", size: [0.1, 0.1, 0.1], pos: [0, 0, 0], colour: "#00ff00", material: "glow", repeat: { count: 99, mode: "line" }, anim: "flicker" },
  ] });
  assert.equal(r.name, "a tower");
  assert.equal(r.animation, "none");
  const [box, sphere] = r.parts;
  assert.deepEqual(box.size, [1.2, 0.02, 0.2]);
  assert.deepEqual(box.pos, [0.8, 0, 0.1]);
  assert.deepEqual(box.rot, [180, 0, 0]);
  assert.equal(box.colour, "#abcdef");
  assert.equal(box.material, "stone");
  assert.equal(box.anim, undefined);
  assert.deepEqual(sphere.repeat, { count: 12, mode: "line", spacing: 0.15 });
  assert.equal(normaliseRecipe({ parts: [] }), null);
  assert.equal(normaliseRecipe(null), null);
});

test("expandParts unrolls rings and lines", () => {
  const parts = expandParts({ parts: [
    { shape: "box", size: [0.1, 0.1, 0.1], pos: [0, 0.5, 0], colour: "#000000", material: "stone", repeat: { count: 4, mode: "ring", radius: 0.2 } },
    { shape: "box", size: [0.1, 0.1, 0.1], pos: [0, 0, 0], colour: "#000000", material: "stone", repeat: { count: 3, mode: "line", spacing: 0.1 } },
  ] });
  assert.equal(parts.length, 7);
  assert.ok(Math.abs(parts[0].pos[0] - 0.2) < 1e-9 && Math.abs(parts[1].pos[2] - 0.2) < 1e-9);
  assert.deepEqual(parts.slice(4).map((p) => Math.round(p.pos[0] * 10) / 10), [-0.1, 0, 0.1]);
});

test("every sprite archetype has a generator that makes a valid, bounded model", () => {
  for (const key of SPRITE_KEYS) {
    assert.ok(GENERATOR_KEYS.includes(key), key);
    for (const aspect of [0.3, 1, 2.5]) {
      const r = proceduralRecipe(key, 0.37, aspect);
      assert.ok(r && r.parts.length >= 2, `${key} at ${aspect}`);
      assert.deepEqual(normaliseRecipe(r), r, `${key} is already normalised`);
      assert.ok(expandParts(r).length <= MAX_EXPANDED);
    }
  }
});

test("procedural models are deterministic per seed and differ between seeds", () => {
  assert.deepEqual(proceduralRecipe("castle", 0.5, 1), proceduralRecipe("castle", 0.5, 1));
  const looks = new Set([0.1, 0.2, 0.3, 0.4, 0.5, 0.6].map((s) => JSON.stringify(proceduralRecipe("tower", s, 0.5).parts)));
  assert.ok(looks.size >= 5, `only ${looks.size} distinct towers`);
});

test("wide objects get wider models", () => {
  const width = (r) => {
    const xs = expandParts(r).flatMap((p) => [p.pos[0] - p.size[0] / 2, p.pos[0] + p.size[0] / 2]);
    return Math.max(...xs) - Math.min(...xs);
  };
  assert.ok(width(proceduralRecipe("village", 0.2, 1.5)) > width(proceduralRecipe("village", 0.2, 0.5)));
});

test("fitScale covers the box but never balloons a wide model", () => {
  const tall = { w: 0.4, h: 1, d: 0.4 };
  assert.ok(fitScale(tall, 50, 200) * tall.h >= 200);              // covers a bottle's height
  const flat = { w: 1.4, h: 0.5, d: 0.6 };
  assert.ok(fitScale(flat, 50, 200) * flat.w <= 50 * MAX_WIDEN + 1e-9);
});

test("models turn with their place across the view", () => {
  assert.ok(yawFor(0.1, 0.5) > 0 && yawFor(0.9, 0.5) < 0);
  assert.equal(yawFor(0.5, 0.5), 0);
});
