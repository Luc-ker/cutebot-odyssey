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

test("default provider is the local renderer", () => assert.equal(PROVIDER, "local"));

test("local provider draws through the compositor and reports its frames", async () => {
  let frameCb = null;
  const looks = [];
  const out = { id: "composited" };
  const subs = [];
  const compositor = {
    scene: { onVision() {}, onObjects() {}, reset() {} },
    onFrame(cb) { frameCb = cb; return () => { frameCb = null; }; },
    async start() { return out; },
    stop() {},
    setLook(l) { looks.push(l); },
  };
  let t = 0, tick = null;
  const r = createRestyler({ RESTYLE_PROVIDER: "local", STABLE_KINGDOM_ENABLED: true, STABLE_KINGDOM_PROMPT: "a kingdom" }, {
    now: () => t, setInterval: (fn) => { tick = fn; return 1; }, clearInterval: () => {},
    hub: { sub: (topic) => { subs.push(topic); return () => {}; } },
    loadCompositor: async () => ({ createCompositor: () => compositor }),
  });
  r.setPrompt("a kingdom");
  assert.equal(await r.start({}), out);
  assert.deepEqual(subs.sort(), ["system.reset", "vision.state", "world.models", "world.objects"]); // stable: no world looks
  assert.ok(looks.length >= 1 && looks.at(-1).tintAmount > 0);
  frameCb();
  assert.equal(r.status.ok, true);
  t = 2000; tick();
  assert.equal(r.status.ok, false); // no frames for 1.5 s
  assert.equal(r.provider.compositor, compositor);
});

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
  const r = createRestyler({ RESTYLE_PROVIDER: "fake" }, {
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

test("Decart fetches a fresh same-origin token and surfaces server failure", async () => {
  const { fetchDecartToken } = await import("./restyler.js");
  let calls = 0;
  const fetcher = async (url, options) => {
    assert.equal(url, "/api/restyle/token");
    assert.equal(options.headers["X-Genrator-Restyle"], "1");
    assert.equal(options.cache, "no-store");
    calls++;
    return { ok: true, json: async () => ({ apiKey: `token-${calls}` }) };
  };
  assert.equal(await fetchDecartToken(fetcher), "token-1");
  assert.equal(await fetchDecartToken(fetcher), "token-2");
  await assert.rejects(fetchDecartToken(async () => ({
    ok: false, json: async () => ({ error: "Decart rejected token request (HTTP 401)" }),
  })), /HTTP 401/);
});

test("Decart publishes an owned model-sized stream, refreshes tokens and cleans up", async () => {
  const input = { id: "phone" }, normalized = { id: "normalized" }, remote = { id: "remote" };
  let stopped = 0, disconnected = 0, unwatch = 0, tokens = 0;
  const rt = { on() {}, setPrompt() {}, disconnect() { disconnected++; } };
  const r = createRestyler({ RESTYLE_PROVIDER: "decart" }, {
    setInterval: () => 1, clearInterval() {},
    makeDecartSurface(options) {
      assert.deepEqual(options, { width: 1280, height: 704, fps: 30, neutral: true });
      return { async start(source) { assert.equal(source, input); return normalized; }, stop() { stopped++; } };
    },
    watchFrames(stream, onFrame) { assert.equal(stream, remote); onFrame(); return () => { unwatch++; }; },
    fetch: async () => ({ ok: true, json: async () => ({ apiKey: `ephemeral-${++tokens}` }) }),
    loadDecartSdk: async () => ({
      models: { realtime: () => ({ width: 1280, height: 704, fps: 30 }) },
      createDecartClient(options) {
        assert.equal(options.apiKey, undefined);
        return { realtime: { async connect(source, settings) {
          assert.equal(source, normalized);
          assert.equal(await options.apiKeyProvider(), "ephemeral-1");
          assert.equal(await options.apiKeyProvider(), "ephemeral-2");
          assert.equal(settings.initialState.prompt.text, "Kingdom");
          settings.onRemoteStream(remote);
          return rt;
        } } };
      },
    }),
  });
  r.setPrompt("Kingdom");
  assert.equal(await r.start(input), remote);
  assert.equal(r.status.ok, true);
  r.stop();
  assert.equal(disconnected, 1);
  assert.equal(stopped, 1);
  assert.equal(unwatch, 1);
});

test("failed Decart start stops its canvas and watchdog", async () => {
  let stops = 0, clears = 0;
  const r = createRestyler({ RESTYLE_PROVIDER: "decart" }, {
    setInterval: () => 1, clearInterval() { clears++; },
    makeDecartSurface: () => ({ start: async () => ({}), stop() { stops++; } }),
    loadDecartSdk: async () => ({ models: { realtime: () => ({}) },
      createDecartClient: () => ({ realtime: { connect: async () => { throw new Error("denied"); } } }),
    }),
  });
  await assert.rejects(r.start({}), /denied/);
  assert.equal(stops, 1);
  assert.equal(clears, 1);
  assert.equal(r.status.ok, false);
});

test("late Decart connection cannot replace or stop the next phone session", async () => {
  let finishOld, oldSettings, newSettings, calls = 0;
  const stopped = [], disconnected = [];
  const sdk = {
    models: { realtime: () => ({}) },
    createDecartClient: () => ({ realtime: { connect: async (input, settings) => {
      calls++;
      const rt = { on() {}, setPrompt() {}, disconnect() { disconnected.push(input.id); } };
      if (calls === 1) { oldSettings = settings; await new Promise(resolve => { finishOld = resolve; }); }
      else { newSettings = settings; settings.onRemoteStream({ id: 'new-remote' }); }
      return rt;
    } } }),
  };
  const r = createRestyler({ RESTYLE_PROVIDER: "decart" }, {
    setInterval: () => 1, clearInterval() {}, loadDecartSdk: async () => sdk,
    makeDecartSurface: () => { let id; return {
      async start(source) { id = source.id; return source; }, stop() { stopped.push(id); },
    }; },
    watchFrames: (stream, frame) => { frame(); return () => {}; },
  });
  const old = r.start({ id: 'old' });
  const rejected = assert.rejects(old, /Renderer stopped/);
  while (!finishOld) await new Promise(resolve => setImmediate(resolve));
  assert.equal((await r.start({ id: 'new' })).id, 'new-remote');
  oldSettings.onRemoteStream({ id: 'stale' });
  finishOld();
  await rejected;
  assert.deepEqual(disconnected, ['old']);
  assert.deepEqual(stopped, ['old']);
  assert.equal(r.status.ok, true);
  assert.ok(newSettings);
  r.stop();
  assert.deepEqual(disconnected, ['old', 'new']);
  assert.deepEqual(stopped, ['old', 'new']);
});

import { stablePrompt } from "./restyler.js";

test("stablePrompt locks the Kingdom prompt only in stable mode", () => {
  assert.equal(stablePrompt({}), null);
  assert.equal(stablePrompt({ STABLE_KINGDOM_ENABLED: false, STABLE_KINGDOM_PROMPT: "x" }), null);
  assert.equal(stablePrompt({ STABLE_KINGDOM_ENABLED: true, STABLE_KINGDOM_PROMPT: "  " }), null);
  assert.equal(stablePrompt({ STABLE_KINGDOM_ENABLED: true, STABLE_KINGDOM_PROMPT: " a miniature kingdom " }),
    "a miniature kingdom");
  assert.equal(stablePrompt({ STABLE_KINGDOM_ENABLED: true, STABLE_KINGDOM_PROMPT: "y".repeat(500) }).length, 400);
});

test("a prompt set before start reaches the renderer at connect time", async () => {
  const seen = [];
  const r = createRestyler({ RESTYLE_PROVIDER: "fake" }, {
    now: () => 0, setInterval: () => 1, clearInterval: () => {},
    makeSurface: () => ({ async start(_s, _f, getTint) { seen.push(getTint()); return {}; }, stop() {} }),
  });
  r.setPrompt("a miniature kingdom");
  await r.start({});
  assert.ok(seen[0].strength > 0); // "kingdom" tint applied from the first frame
});
