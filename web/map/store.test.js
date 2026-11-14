// node --test web/map/store.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createStore } from "./store.js";

function clock(start = 10) {
  let t = start;
  return { now: () => t, set: (v) => { t = v; } };
}

const env = (topic, data) => ({ topic, ts: 0, src: "test", data });

test("keeps the latest message per topic", () => {
  const c = clock();
  const s = createStore({ now: c.now });
  s.apply(env("robot.state", { pos: [0.1, 0.1] }));
  s.apply(env("world.current", { world: { id: "w-1" } }));
  c.set(11);
  s.apply(env("robot.state", { pos: [0.2, 0.3] }));
  assert.deepEqual(s.state["robot.state"], { pos: [0.2, 0.3] });
  assert.equal(s.state["world.current"].world.id, "w-1");
  assert.equal(s.state.received["robot.state"], 11);
  assert.equal(s.state.received["world.current"], 10);
});

test("records beat time on arrival, with the local clock", () => {
  const c = clock(42);
  const s = createStore({ now: c.now });
  assert.equal(s.state.lastBeatT, null);
  s.apply(env("audio.beat", { tempo_bpm: 128, strength: 0.7 }));
  assert.equal(s.state.lastBeatT, 42);
  assert.equal(s.state["audio.beat"].tempo_bpm, 128);
  c.set(42.5);
  s.apply(env("audio.features", { rms: 0.1, energy: 0.4, brightness: 0.5, silent: false }));
  assert.equal(s.state.lastBeatT, 42); // other audio topics don't move it
});

test("world events are kept as a list, not just the latest", () => {
  const s = createStore({ now: clock().now });
  const before = s.state.seq;
  s.apply(env("world.event", { kind: "giant_enter", id: "g1" }));
  s.apply(env("world.event", { kind: "danger_enter", id: 4 }));
  assert.deepEqual(s.eventsSince(before).map((e) => e.kind), ["giant_enter", "danger_enter"]);
  assert.equal(s.state["world.event"].kind, "danger_enter");
  for (let i = 0; i < 100; i++) s.apply(env("world.event", { kind: "horn" }));
  assert.equal(s.state.events.length, 40);
});

test("health is merged per service; transitions are stamped", () => {
  const s = createStore({ now: clock(5).now });
  s.apply(env("system.health", { service: "jetson", ok: true, detail: "" }));
  s.apply(env("system.health", { service: "gemini", ok: false, detail: "timeout" }));
  assert.equal(s.state.health.jetson.ok, true);
  assert.equal(s.state.health.gemini.ok, false);
  s.apply(env("world.transition", { from: null, to: { id: "w-2" }, duration_ms: 3000 }));
  assert.equal(s.state.transition._t, 5);
  assert.equal(s.state.transition.to.id, "w-2");
});

test("system.reset clears state but keeps config", () => {
  const s = createStore({ now: clock().now, config: { DANGER_RADIUS: 0.12 } });
  s.apply(env("world.current", { world: { id: "w-1" } }));
  s.apply(env("audio.beat", { tempo_bpm: 100 }));
  const seq = s.state.seq;
  s.apply(env("system.reset", {}));
  assert.equal(s.state["world.current"], undefined);
  assert.equal(s.state.lastBeatT, null);
  assert.equal(s.state.config.DANGER_RADIUS, 0.12);
  assert.ok(s.state.seq > seq);
});

test("ignores junk", () => {
  const s = createStore();
  assert.doesNotThrow(() => { s.apply(null); s.apply({}); s.apply({ topic: 3 }); });
});
