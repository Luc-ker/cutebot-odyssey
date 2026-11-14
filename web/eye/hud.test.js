// node --test web/eye/hud.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { mountHud, localColour, prettyRole } from "./hud.js";

// --- minimal DOM stub ------------------------------------------------------------------------
function makeDoc() {
  const doc = {
    createElement(tag) {
      const cls = new Set();
      const el = {
        tagName: tag.toUpperCase(), ownerDocument: doc, children: [], textContent: "", props: {},
        set className(v) { cls.clear(); v.split(/\s+/).filter(Boolean).forEach((c) => cls.add(c)); },
        get className() { return [...cls].join(" "); },
        classList: {
          add: (c) => cls.add(c), remove: (c) => cls.delete(c), contains: (c) => cls.has(c),
          toggle: (c, on = !cls.has(c)) => (on ? cls.add(c) : cls.delete(c), on),
        },
        style: { setProperty(k, v) { el.props[k] = v; } },
        append(...kids) { el.children.push(...kids); },
        remove() {},
        find(c) { return el.children.find((k) => k.classList.contains(c)) ?? el.children.map((k) => k.find?.(c)).find(Boolean); },
      };
      return el;
    },
  };
  return doc;
}

function fakeHub() {
  const subs = [];
  return {
    sub(p, cb) { subs.push([p, cb]); return () => {}; },
    emit(topic, data) { for (const [p, cb] of subs) if (p === topic) cb({ topic, data }); },
  };
}

function fakeTimers() {
  let t = 0;
  const pending = new Map();
  let next = 1;
  return {
    setTimeout: (fn, ms) => { pending.set(next, [t + ms, fn]); return next++; },
    clearTimeout: (id) => pending.delete(id),
    advance(ms) {
      t += ms;
      for (const [id, [at, fn]] of [...pending]) if (at <= t) { pending.delete(id); fn(); }
    },
  };
}

function setup() {
  const doc = makeDoc();
  const container = doc.createElement("div");
  const hub = fakeHub();
  const timers = fakeTimers();
  mountHud(container, hub, { colourFor: (w) => localColour(w), ...timers });
  const root = container.children[0];
  return { hub, timers, root, ahead: root.find("hud-ahead"), world: root.find("hud-world"), beat: root.find("hud-beat") };
}

const objects = { world_id: "w-1", objects: [
  { id: 3, cls: "boat", role: "ship", name: "The Salt Queen" },
  { id: 9, cls: "cup", role: "sea_serpent", name: "The Coil" },
] };

test("facing id -> label shows name and role", () => {
  const k = setup();
  k.hub.emit("world.objects", objects);
  k.hub.emit("robot.state", { facing_id: 3 });
  assert.equal(k.ahead.textContent, "Ahead: The Salt Queen (ship)");
  assert.ok(k.ahead.classList.contains("visible"));

  k.hub.emit("robot.state", { facing_id: 9 });
  assert.equal(k.ahead.textContent, "Ahead: The Coil (sea serpent)");
});

test("label fades 2 s after the target goes, and stays if it comes back", () => {
  const k = setup();
  k.hub.emit("world.objects", objects);
  k.hub.emit("robot.state", { facing_id: 3 });
  k.hub.emit("robot.state", { facing_id: null });
  k.timers.advance(1500);
  assert.ok(k.ahead.classList.contains("visible"));
  k.hub.emit("robot.state", { facing_id: 3 }); // back on target cancels the fade
  k.timers.advance(1000);
  assert.ok(k.ahead.classList.contains("visible"));
  k.hub.emit("robot.state", { facing_id: null });
  k.timers.advance(2000);
  assert.ok(!k.ahead.classList.contains("visible"));
});

test("unknown facing id shows nothing", () => {
  const k = setup();
  k.hub.emit("robot.state", { facing_id: 42 });
  assert.ok(!k.ahead.classList.contains("visible"));
});

test("world name shows and is tinted by the palette", async () => {
  const k = setup();
  k.hub.emit("world.current", { world: { id: "w-1", world: { name: "The Drowned Kingdom",
    palette: ["deep teal", "storm grey", "lantern gold"] } } });
  assert.equal(k.world.textContent, "The Drowned Kingdom");
  await new Promise((r) => setImmediate(r));
  assert.equal(k.world.props["--hud-accent"], "rgb(230,180,50)");
});

test("beat pops the dot", () => {
  const k = setup();
  k.hub.emit("audio.beat", { tempo_bpm: 120, strength: 0.8 });
  assert.ok(k.beat.classList.contains("pop"));
  k.timers.advance(200);
  assert.ok(!k.beat.classList.contains("pop"));
});

test("prettyRole", () => assert.equal(prettyRole("lava_beast"), "lava beast"));
