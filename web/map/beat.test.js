// node --test web/map/beat.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { beatEnvelope, beatFromState, periodFor, MAX_PREDICTED } from "./beat.js";

const T0 = 100;
const BPM = 120; // period 0.5 s

test("1 at the beat", () => {
  assert.equal(beatEnvelope(T0, T0, BPM, 1), 1);
});

test("< 0.2 halfway to the next beat", () => {
  const half = periodFor(BPM) / 2;
  assert.ok(beatEnvelope(T0 + half, T0, BPM, 1) < 0.2);
  assert.ok(beatEnvelope(T0 + half, T0, BPM, 1, { anticipate: false }) < 0.2);
});

test("0 when silent", () => {
  assert.equal(beatEnvelope(T0, T0, BPM, 1, { silent: true }), 0);
});

test("decays monotonically over 40 % of the period", () => {
  const p = periodFor(BPM);
  const samples = [0, 0.1, 0.2, 0.3, 0.39].map((f) => beatEnvelope(T0 + f * p, T0, BPM, 1));
  for (let i = 1; i < samples.length; i++) assert.ok(samples[i] < samples[i - 1], samples.join(","));
  assert.equal(beatEnvelope(T0 + 0.41 * p, T0, BPM, 1, { anticipate: false }), 0);
});

test("scaled by energy", () => {
  const quiet = beatEnvelope(T0, T0, BPM, 0);
  const mid = beatEnvelope(T0, T0, BPM, 0.5);
  assert.ok(quiet > 0 && quiet < mid && mid < 1);
});

test("anticipation fires on the predicted next beat, then stops", () => {
  const p = periodFor(BPM);
  assert.ok(beatEnvelope(T0 + p, T0, BPM, 1) > 0.999);         // predicted beat
  assert.ok(beatEnvelope(T0 + p - 0.01, T0, BPM, 1) > 0);       // attack starts just before
  assert.equal(beatEnvelope(T0 + p, T0, BPM, 1, { anticipate: false }), 0);
  assert.equal(beatEnvelope(T0 + (MAX_PREDICTED + 1) * p, T0, BPM, 1), 0);
});

test("no beat yet, bad numbers and future beats give 0", () => {
  assert.equal(beatEnvelope(T0, null, BPM, 1), 0);
  assert.equal(beatEnvelope(T0, undefined, BPM, 1), 0);
  assert.equal(beatEnvelope(T0, T0 + 1, BPM, 1), 0);
  assert.ok(beatEnvelope(T0, T0, undefined, 1) === 1); // missing tempo defaults to 120
});

test("beatFromState reads the store", () => {
  const state = { lastBeatT: T0, "audio.beat": { tempo_bpm: 90, strength: 0.8 }, "audio.features": { energy: 1, silent: false } };
  assert.equal(beatFromState(state, T0), 1);
  assert.equal(beatFromState({ ...state, "audio.features": { energy: 1, silent: true } }, T0), 0);
  assert.equal(beatFromState({}, T0), 0);
});
