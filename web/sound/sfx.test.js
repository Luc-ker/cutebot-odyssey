// node --test web/sound/sfx.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createSfx, resolveName, soundNames, SETTINGS, FALLBACK, RECIPES } from "./sfx.js";

// --- a fake AudioContext that records what was started --------------------------------------------
function param() {
  const calls = [];
  const p = { value: 0, calls };
  for (const m of ["setValueAtTime", "linearRampToValueAtTime", "exponentialRampToValueAtTime", "setTargetAtTime"]) {
    p[m] = (v, t) => {
      if (!Number.isFinite(v) || !Number.isFinite(t)) throw new Error(`${m}(${v}, ${t}) not finite`);
      if (m === "exponentialRampToValueAtTime" && v <= 0) throw new Error("exponential ramp to <= 0");
      calls.push([m, v, t]);
      return p;
    };
  }
  return p;
}

function fakeCtx() {
  const ctx = {
    currentTime: 1,
    sampleRate: 8000,
    state: "suspended",
    destination: { kind: "destination" },
    started: [],
    resumed: 0,
    resume() { ctx.state = "running"; ctx.resumed += 1; return Promise.resolve(); },
  };
  const node = (kind, extra = {}) => {
    const n = {
      kind, connections: [],
      connect(dest) { n.connections.push(dest); return dest; },
      start(t) { ctx.started.push({ kind, t }); },
      stop() {},
      ...extra,
    };
    return n;
  };
  ctx.createOscillator = () => node("osc", { type: "sine", frequency: param(), detune: param() });
  ctx.createGain = () => node("gain", { gain: param() });
  ctx.createBiquadFilter = () => node("filter", { type: "lowpass", frequency: param(), Q: param() });
  ctx.createBufferSource = () => node("noise", { buffer: null, loop: false });
  ctx.createBuffer = (_ch, len) => ({ data: new Float32Array(len), getChannelData() { return this.data; } });
  return ctx;
}

// ---- acceptance -----------------------------------------------------------------------------------

test('play("unknown") plays the fallback without throwing', () => {
  const ctx = fakeCtx();
  const sfx = createSfx({ ctx });
  let played;
  assert.doesNotThrow(() => { played = sfx.play("unknown"); });
  assert.equal(played, FALLBACK);
  assert.ok(ctx.started.length > 0, "fallback started some oscillators");
});

// ---- coverage of names ----------------------------------------------------------------------------

test("core names and one horn per fallback setting exist", () => {
  for (const n of ["warning", "chime", "landing", "whoosh", "bell"]) assert.ok(RECIPES[n], n);
  assert.equal(SETTINGS.length, 8);
  for (const s of SETTINGS) assert.ok(RECIPES[`horn_${s}`], `horn_${s}`);
});

test("every sfx in shared/roles.json has its own sound", () => {
  const roles = JSON.parse(readFileSync(new URL("../../shared/roles.json", import.meta.url), "utf8"));
  const missing = [...new Set(roles.map((r) => r.sfx).filter(Boolean))].filter((n) => !RECIPES[n]);
  assert.deepEqual(missing, []);
});

test("every named sound plays without throwing and starts something", () => {
  for (const name of soundNames()) {
    const ctx = fakeCtx();
    const sfx = createSfx({ ctx });
    assert.equal(sfx.play(name), name);
    assert.ok(ctx.started.length > 0, `${name} started nothing`);
    assert.ok(ctx.started.every((s) => s.t >= ctx.currentTime), `${name} scheduled in the past`);
  }
});

test("resolveName ignores prototype keys", () => {
  assert.equal(resolveName("toString"), FALLBACK);
  assert.equal(resolveName(undefined), FALLBACK);
  assert.equal(resolveName("bell"), "bell");
});

// ---- ducking, unlocking ------------------------------------------------------------------------------

test("duck lowers effects to 50 % and restores them", () => {
  const ctx = fakeCtx();
  const gains = [];
  const mk = ctx.createGain;
  ctx.createGain = () => { const g = mk(); gains.push(g); return g; };
  const sfx = createSfx({ ctx });
  sfx.duck(true);
  sfx.duck(false);
  // The ducker is the gain node wired straight to the destination.
  const ducker = gains.find((g) => g.connections.includes(ctx.destination));
  const targets = ducker.gain.calls.filter(([m]) => m === "setTargetAtTime").map(([, v]) => v);
  assert.deepEqual(targets, [0.5, 1]);
});

test("unlock resumes a suspended context", async () => {
  const ctx = fakeCtx();
  const sfx = createSfx({ ctx });
  assert.equal(await sfx.unlock(), true);
  assert.equal(ctx.resumed, 1);
});

test("without any AudioContext, play returns null instead of throwing", () => {
  const sfx = createSfx({ AudioContext: null, ctx: null });
  // Node has no AudioContext global, so nothing can be created.
  if (globalThis.AudioContext) return;
  assert.equal(sfx.play("warning"), null);
});
