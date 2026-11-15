// node --test web/eye/looks.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { LOOKS, lookForPrompt, lookForWorld, lookKey } from "./looks.js";

const worldsDir = fileURLToPath(new URL("../../shared/worlds/", import.meta.url));

test("every fallback world gets its own look", () => {
  const keys = readdirSync(worldsDir).filter((f) => f.endsWith(".json")).map((f) => {
    const world = JSON.parse(readFileSync(worldsDir + f, "utf8"));
    const look = lookForWorld(world);
    assert.ok(look.tint.length === 3 && look.particles, f);
    return lookKey(`${world.world.setting} ${world.world.name}`) ?? lookKey(world.restyle_prompt);
  });
  assert.ok(keys.every(Boolean), `unmatched world: ${keys}`);
  assert.equal(new Set(keys).size, keys.length, `two worlds share a look: ${keys}`);
});

test("night worlds are darker", () => {
  const day = lookForWorld({ world: { setting: "medieval kingdom", time_of_day: "morning" } });
  const night = lookForWorld({ world: { setting: "medieval kingdom", time_of_day: "night" } });
  assert.ok(night.brightness < day.brightness);
});

test("prompts map to looks, unknown ones to a mild tint", () => {
  assert.equal(lookForPrompt("a sunlit medieval kingdom").tint, LOOKS.kingdom.tint);
  const plain = lookForPrompt("a quiet room");
  assert.equal(plain.tintAmount, 0);
  assert.equal(plain.particles.kind, "none");
});
