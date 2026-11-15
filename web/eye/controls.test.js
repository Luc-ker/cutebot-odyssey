// node --test web/eye/controls.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { mountControls, nextShowSet } from "./controls.js";

function makeDoc() {
  const listeners = {};
  const body = { cls: new Set(), classList: null };
  body.classList = { add: (c) => body.cls.add(c), remove: (c) => body.cls.delete(c), contains: (c) => body.cls.has(c) };
  const doc = {
    body,
    addEventListener: (t, fn) => { (listeners[t] ??= []).push(fn); },
    removeEventListener: () => {},
    fire: (t, e) => (listeners[t] ?? []).forEach((fn) => fn(e)),
    createElement(tag) {
      const cls = new Set();
      const attrs = {};
      const handlers = {};
      const el = {
        tagName: tag.toUpperCase(), children: [], textContent: "", hidden: false, disabled: false,
        set className(v) { cls.clear(); v.split(/\s+/).filter(Boolean).forEach((c) => cls.add(c)); },
        get className() { return [...cls].join(" "); },
        classList: { add: (c) => cls.add(c), remove: (c) => cls.delete(c), contains: (c) => cls.has(c),
          toggle: (c, on = !cls.has(c)) => (on ? cls.add(c) : cls.delete(c), on) },
        setAttribute: (k, v) => { attrs[k] = String(v); },
        getAttribute: (k) => attrs[k],
        addEventListener: (t, fn) => { handlers[t] = fn; },
        click: () => handlers.click?.(),
        append(...kids) { el.children.push(...kids); },
        remove() {},
      };
      return el;
    },
  };
  return doc;
}

function setup() {
  const doc = makeDoc();
  const container = doc.createElement("div");
  container.ownerDocument = doc;
  const subs = [];
  const sent = [];
  const hub = {
    sub(p, cb) { subs.push([p, cb]); return () => {}; },
    pub(t, d) { sent.push([t, d]); },
    emit(t, d) { subs.filter(([p]) => p === t).forEach(([, cb]) => cb({ topic: t, data: d })); },
  };
  const states = [];
  const ctl = mountControls(container, hub, { onState: (s) => states.push(s), setTimeout: () => 1, clearTimeout: () => {} });
  const [show, listen] = ctl.root.children;
  return { doc, hub, sent, states, ctl, show, listen };
}

test("nextShowSet flips only the pressed control", () => {
  assert.deepEqual(nextShowSet({ running: true, listening: true }, "show"), { running: false });
  assert.deepEqual(nextShowSet({ running: true, listening: false }, "listen"), { listening: true });
});

test("mounting asks the brain for its state", () => {
  const k = setup();
  assert.deepEqual(k.sent, [["show.set", {}]]);
});

test("buttons ask the brain and only change when show.state answers", () => {
  const k = setup();
  k.sent.length = 0;
  k.show.click();
  assert.deepEqual(k.sent, [["show.set", { running: false }]]);
  assert.equal(k.show.getAttribute("aria-pressed"), "true"); // unchanged until the brain answers
  k.hub.emit("show.state", { running: false, listening: true, can_listen: true });
  assert.equal(k.show.getAttribute("aria-pressed"), "false");
  assert.equal(k.listen.disabled, true);                         // nothing to listen for while stopped
  assert.deepEqual(k.states.at(-1), { running: false, listening: true, can_listen: true });
  k.listen.click();
  assert.equal(k.sent.length, 1);
});

test("listen toggles, and hides when the brain has no microphone", () => {
  const k = setup();
  k.hub.emit("show.state", { running: true, listening: true, can_listen: true });
  k.listen.click();
  assert.deepEqual(k.sent.at(-1), ["show.set", { listening: false }]);
  k.hub.emit("show.state", { running: true, listening: false, can_listen: false });
  assert.equal(k.listen.hidden, true);
});

test("Space and M are shortcuts, and they wake the controls", () => {
  const k = setup();
  k.hub.emit("show.state", { running: true, listening: true, can_listen: true });
  k.sent.length = 0;
  k.doc.fire("keydown", { key: " ", preventDefault() {} });
  k.doc.fire("keydown", { key: "M" });
  assert.deepEqual(k.sent, [["show.set", { running: false }], ["show.set", { listening: false }]]);
  assert.ok(k.doc.body.classList.contains("awake"));
});
