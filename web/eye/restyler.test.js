// node --test web/eye/restyler.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRestyler, tintForPrompt, PROVIDER } from "./restyler.js";

function rig() {
  let t = 0;
  let tick = null;
  let frame = null;
  const out = { id: "styled" };
  const deps = {
    now: () => t,
    setInterval: (fn) => { tick = fn; return 1; },
    clearInterval: () => { tick = null; },
    makeSurface: () => ({
      async start(stream, onFrame) { frame = onFrame; return out; },
      stop() {},
    }),
  };
  const r = createRestyler({ RESTYLE_PROVIDER: "fake" }, deps);
  const statuses = [];
  r.onStatus((s) => statuses.push(s));
  return {
    r, out, statuses,
    advance(ms) { // move the clock in 50 ms steps, running the watchdog like setInterval would
      for (let i = 0; i < ms; i += 50) { t += 50; tick?.(); }
    },
    frame: () => frame(),
  };
}

test("default provider is the fake one", () => assert.equal(PROVIDER, "fake"));

test("tintForPrompt maps keywords to colours", () => {
  const lava = tintForPrompt("a volcanic wasteland, rivers of lava");
  const sea = tintForPrompt("stormy ocean at dusk");
  assert.ok(lava.rgb[0] > lava.rgb[2], "lava is red-orange");
  assert.ok(sea.rgb[2] > sea.rgb[0], "sea is blue");
  assert.equal(sea.dark, true);
  assert.equal(tintForPrompt("").strength, 0);
});

test("fake provider: setPrompt changes the tint", () => {
  const { r } = rig();
  r.setPrompt("a snowy night");
  const snow = r.provider.tint;
  r.setPrompt("a volcanic wasteland");
  assert.notDeepEqual(r.provider.tint.rgb, snow.rgb);
  assert.deepEqual(r.provider.tint, tintForPrompt("a volcanic wasteland"));
});

test("frames -> ok:true; no frames for 1.5 s -> ok:false", async () => {
  const k = rig();
  const stream = await k.r.start({ id: "raw" });
  assert.equal(stream, k.out);

  k.frame();
  assert.equal(k.statuses.at(-1).ok, true);

  for (let i = 0; i < 10; i++) { k.advance(100); k.frame(); } // 1 s of steady frames
  assert.equal(k.r.status.ok, true);
  assert.ok(k.r.status.fps >= 9, `fps ${k.r.status.fps}`);

  k.advance(1400);
  assert.equal(k.r.status.ok, true, "still ok just under 1.5 s");
  k.advance(150);
  assert.equal(k.r.status.ok, false);
  assert.equal(k.statuses.at(-1).ok, false);

  k.frame();
  assert.equal(k.statuses.at(-1).ok, true, "recovers on the next frame");
});

test("never any frame -> ok:false after the 1.5 s grace", async () => {
  const k = rig();
  await k.r.start({});
  k.advance(1600);
  assert.equal(k.r.status.ok, false);
});

test("start failure reports ok:false and rethrows", async () => {
  const statuses = [];
  const r = createRestyler({}, {
    setInterval: () => 1, clearInterval: () => {},
    makeSurface: () => ({ start: async () => { throw new Error("boom"); }, stop() {} }),
  });
  r.onStatus((s) => statuses.push(s));
  await assert.rejects(r.start({}), /boom/);
  assert.equal(statuses.at(-1).ok, false);
});

test("unknown provider throws", () => {
  assert.throws(() => createRestyler({ RESTYLE_PROVIDER: "nope" }), /unknown restyle provider/);
});
