// node --test web/map/icons/icons.test.js — every icon named in shared/roles.json has an SVG (T88).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";

const dir = new URL("./", import.meta.url);
const roles = JSON.parse(readFileSync(new URL("../../../shared/roles.json", import.meta.url), "utf8"));
const files = new Set(readdirSync(dir).filter((f) => f.endsWith(".svg")).map((f) => f.slice(0, -4)));

test("every roles.json icon has a file", () => {
  const missing = [...new Set(roles.map((r) => r.icon))].filter((i) => !files.has(i));
  assert.deepEqual(missing, []);
});

test("system icons exist", () => {
  for (const i of ["unknown", "robot", "giant_hand"]) assert.ok(files.has(i), i);
});

test("icons are 64x64 and tintable with currentColor", () => {
  for (const name of files) {
    const svg = readFileSync(new URL(`${name}.svg`, dir), "utf8");
    assert.match(svg, /viewBox="0 0 64 64"/, name);
    assert.match(svg, /fill="currentColor"/, name);
  }
});
