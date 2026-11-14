import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setSchemas, validateEnvelope, checkEnvelope } from "./schemas.js";

const doc = JSON.parse(readFileSync(new URL("../../shared/schemas/topics.schema.json", import.meta.url)));
const { valid, invalid } = doc._samples;

test("envelope shape is checked before schemas load", () => {
  const res = checkEnvelope({ topic: "audio.beat", ts: 1, src: "x", data: {} });
  assert.deepEqual(res.errors, []);
  assert.match(res.warnings[0], /not loaded/);
  assert.ok(validateEnvelope({ topic: "audio.beat", ts: "now", src: "x", data: {} }).length > 0);
});

test("every valid sample passes", () => {
  setSchemas(doc);
  assert.equal(new Set(valid.map((e) => e.topic)).size, Object.keys(doc.topics).length);
  for (const env of valid) assert.deepEqual(validateEnvelope(env), [], env.topic);
});

test("every malformed sample fails (same set as Python)", () => {
  setSchemas(doc);
  for (const c of invalid) assert.ok(validateEnvelope(c.env).length > 0, c.why);
});

test("vision.state pos [2, 0] is rejected with a path", () => {
  setSchemas(doc);
  const env = JSON.parse(JSON.stringify(valid.find((e) => e.topic === "vision.state")));
  env.data.objects[0].pos = [2, 0];
  assert.deepEqual(validateEnvelope(env), ["data.objects[0].pos[0]: 2 is greater than the maximum of 1"]);
});

test("unknown topic is a warning, not an error", () => {
  setSchemas(doc);
  const warnings = [];
  const errors = validateEnvelope({ topic: "custom.thing", ts: 1, src: "x", data: {} }, warnings);
  assert.deepEqual(errors, []);
  assert.equal(warnings.length, 1);
  assert.match(warnings[0], /custom\.thing/);
});

test("world.event kind-specific required fields", () => {
  setSchemas(doc);
  const errors = validateEnvelope({ topic: "world.event", ts: 1, src: "x", data: { kind: "danger_enter", id: 9 } });
  assert.ok(errors.some((e) => e.includes("'name' is required")));
  assert.ok(errors.some((e) => e.includes("'role' is required")));
});

test("non-objects do not throw", () => {
  setSchemas(doc);
  assert.ok(validateEnvelope(null).length > 0);
  assert.ok(validateEnvelope([1]).length > 0);
});
