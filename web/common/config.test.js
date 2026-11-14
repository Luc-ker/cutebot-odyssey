import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { loadConfig, _resetConfigCache } from "./config.js";

const raw = JSON.parse(readFileSync(new URL("../../shared/config.json", import.meta.url)));

function fakeFetch() {
  const calls = [];
  const fn = async (url) => {
    calls.push(url);
    return { ok: true, status: 200, json: async () => raw };
  };
  fn.calls = calls;
  return fn;
}

test("loadConfig fetches once and caches", async () => {
  _resetConfigCache();
  globalThis.fetch = fakeFetch();
  const a = await loadConfig();
  const b = await loadConfig();
  assert.equal(globalThis.fetch.calls.length, 1);
  assert.equal(globalThis.fetch.calls[0], "/shared/config.json");
  assert.equal(a, b);
  assert.equal(a.HUB_PORT, 8765);
  assert.equal(a._doc, undefined);
});

test("concurrent calls share one fetch", async () => {
  _resetConfigCache();
  globalThis.fetch = fakeFetch();
  await Promise.all([loadConfig(), loadConfig(), loadConfig()]);
  assert.equal(globalThis.fetch.calls.length, 1);
});

test("a failed fetch can be retried", async () => {
  _resetConfigCache();
  let n = 0;
  globalThis.fetch = async () => {
    n++;
    if (n === 1) return { ok: false, status: 500, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => raw };
  };
  await assert.rejects(loadConfig());
  const cfg = await loadConfig();
  assert.equal(cfg.HUB_PORT, 8765);
  assert.equal(n, 2);
});
