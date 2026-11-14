// node --test web/eye/fallback.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { mountFallback, createFallbackState } from "./fallback.js";

function makeDoc() {
  const doc = {
    createElement() {
      const cls = new Set();
      const el = {
        ownerDocument: doc, children: [], textContent: "", dataset: {}, props: {},
        set className(v) { cls.clear(); v.split(/\s+/).filter(Boolean).forEach((c) => cls.add(c)); },
        classList: {
          add: (c) => cls.add(c), remove: (c) => cls.delete(c), contains: (c) => cls.has(c),
          toggle: (c, on = !cls.has(c)) => (on ? cls.add(c) : cls.delete(c), on),
        },
        style: { setProperty(k, v) { el.props[k] = v; } },
        append(...kids) { el.children.push(...kids); },
        remove() {},
      };
      return el;
    },
  };
  return doc;
}

function rig() {
  let t = 0;
  let tick = null;
  let statusCb = null;
  const published = [];
  const subs = [];
  const hub = {
    sub(p, cb) { subs.push([p, cb]); return () => {}; },
    pub(topic, data) { published.push({ topic, data }); },
    emit(topic, data) { for (const [p, cb] of subs) if (p === topic) cb({ topic, data }); },
  };
  const restyler = { onStatus(cb) { statusCb = cb; return () => {}; } };
  const doc = makeDoc();
  const container = doc.createElement("div");
  const fb = mountFallback(container, hub, restyler, {
    now: () => t,
    setInterval: (fn) => { tick = fn; return 1; },
    clearInterval: () => {},
    colourFor: () => [1, 2, 3],
  });
  const root = container.children[0];
  return {
    fb, hub, published, root,
    visible: () => root.classList.contains("active"),
    status(ok) { statusCb({ ok, fps: ok ? 25 : 0, latency_ms: 180 }); },
    advance(ms, ok) { // time passes, restyler keeps reporting `ok` every 250 ms
      for (let i = 0; i < ms; i += 250) { t += 250; if (ok !== undefined) this.status(ok); tick(); }
    },
  };
}

test("status false for > 1.5 s -> fallback visible; true for 3 s -> hidden", () => {
  const k = rig();
  k.status(true);
  assert.equal(k.visible(), false);

  k.status(false);
  k.advance(1500, false);
  assert.equal(k.visible(), false, "not yet at exactly 1.5 s");
  k.advance(250, false);
  assert.equal(k.visible(), true);
  assert.equal(k.fb.isActive(), true);

  k.status(true); // restyler recovers now
  k.advance(2750, true);
  assert.equal(k.visible(), true, "needs a full 3 s of ok");
  k.advance(250, true);
  assert.equal(k.visible(), false);
});

test("a brief ok blip does not end the fallback", () => {
  const k = rig();
  k.status(false);
  k.advance(2000, false);
  assert.equal(k.visible(), true);
  k.advance(1000, true);
  k.advance(250, false);
  k.advance(2500, true);
  assert.equal(k.visible(), true);
});

test("publishes video.status on each switch", () => {
  const k = rig();
  k.status(false);
  k.advance(2000, false);
  k.status(true);
  k.advance(3000, true);
  const statuses = k.published.filter((m) => m.topic === "video.status").map((m) => m.data);
  assert.deepEqual(statuses, [{ mode: "raw", latency_ms: 0 }, { mode: "restyled", latency_ms: 180 }]);
});

test("forced raw shows fallback regardless of status", () => {
  const k = rig();
  const changes = [];
  k.fb.onChange((on) => changes.push(on));
  k.status(true);
  k.fb.setForced(true);
  assert.equal(k.visible(), true);
  k.fb.setForced(false);
  assert.equal(k.visible(), false);
  assert.deepEqual(changes, [true, false]);
});

test("facing object's role label is shown large", () => {
  const k = rig();
  k.hub.emit("world.objects", { objects: [{ id: 7, role: "lighthouse", name: "Old Beacon", behaviour: "friendly" }] });
  k.hub.emit("robot.state", { facing_id: 7 });
  const label = k.root.children.find((c) => c.classList.contains("fb-label"));
  assert.equal(label.textContent, "Old Beacon · lighthouse");
  assert.ok(label.classList.contains("visible"));
  assert.equal(label.dataset.behaviour, "friendly");
});

test("pure state machine", () => {
  const s = createFallbackState();
  s.status(false, 0);
  assert.equal(s.evaluate(1500), false);
  assert.equal(s.evaluate(1501), true);
  assert.equal(s.active, true);
  s.status(true, 2000);
  assert.equal(s.evaluate(4999), false);
  assert.equal(s.evaluate(5000), true);
  assert.equal(s.active, false);
});
