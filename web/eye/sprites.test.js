// node --test web/eye/sprites.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { DECAL_KEYS, SPRITE_KEYS, artFor, kingdomRoleForClass, rasterSize } from "./sprites.js";

const here = (p) => fileURLToPath(new URL(p, import.meta.url));

test("every role in shared/roles.json has art", () => {
  const roles = JSON.parse(readFileSync(here("../../shared/roles.json"), "utf8"));
  for (const r of roles) {
    const art = artFor(r.role, r.behaviour);
    const keys = art.kind === "decal" ? DECAL_KEYS : SPRITE_KEYS;
    assert.ok(keys.includes(art.key), `${r.role} -> ${art.key}`);
  }
});

test("flat roles are decals, unknown roles fall back on behaviour", () => {
  assert.deepEqual(artFor("river"), { kind: "decal", key: "water" });
  assert.deepEqual(artFor("watchtower"), { kind: "sprite", key: "tower" });
  assert.deepEqual(artFor("kraken", "threat"), { kind: "sprite", key: "beast" });
  assert.deepEqual(artFor(null), { kind: "sprite", key: "monolith" });
});

test("every sprite key has an SVG file with a viewBox", () => {
  for (const key of SPRITE_KEYS) {
    const path = here(`./sprites/${key}.svg`);
    assert.ok(existsSync(path), key);
    assert.match(readFileSync(path, "utf8"), /<svg[^>]+viewBox="[-\d. ]+"[^>]+width="\d+"[^>]+height="\d+"/, key);
  }
});

test("kingdom class roles match the brain's stable mode table", () => {
  assert.deepEqual(kingdomRoleForClass("bottle"), { role: "watchtower", behaviour: "neutral" });
  assert.equal(kingdomRoleForClass("backpack").behaviour, "threat");
  assert.equal(kingdomRoleForClass("unknown thing").role, "castle");
});

test("rasterSize keeps the aspect ratio", () => {
  assert.deepEqual(rasterSize(110, 280, 384), [151, 384]);
  assert.deepEqual(rasterSize(0, 0, 100), [100, 100]);
});
