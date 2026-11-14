import test from "node:test";
import assert from "node:assert/strict";
import { TOPIC, frameSize, startFrameSender, stripDataUrl } from "./frames.js";

test("frameSize scales down to the target width, keeps aspect, never upscales", () => {
  assert.deepEqual(frameSize(1920, 1080, 640), [640, 360]);
  assert.deepEqual(frameSize(480, 640, 640), [480, 640]); // portrait phone, already small
  assert.deepEqual(frameSize(320, 240, 640), [320, 240]);
  assert.equal(frameSize(0, 0, 640), null);
});

test("stripDataUrl keeps only base64 JPEG payloads", () => {
  assert.equal(stripDataUrl("data:image/jpeg;base64,QUJD"), "QUJD");
  assert.equal(stripDataUrl("data:image/png;base64,QUJD"), null);
  assert.equal(stripDataUrl(undefined), null);
});

function fakes({ ready = 4, vw = 1280, vh = 720 } = {}) {
  const published = [];
  const draws = [];
  const hub = { pub: (topic, data) => published.push({ topic, data }) };
  const video = { readyState: ready, videoWidth: vw, videoHeight: vh };
  const canvas = {
    width: 0, height: 0,
    getContext: () => ({ drawImage: (...a) => draws.push(a) }),
    toDataURL: (type, q) => `data:${type};base64,ZnJhbWU=`,
  };
  let tickFn = null;
  let cleared = false;
  const opts = {
    canvas, hz: 5,
    setInterval: (fn, ms) => { tickFn = fn; assert.equal(ms, 200); return 7; },
    clearInterval: (id) => { cleared = id === 7; },
  };
  return { hub, video, canvas, published, draws, opts, tick: () => tickFn(), wasCleared: () => cleared };
}

test("publishes camera.frame with a small JPEG at the configured rate", () => {
  const f = fakes();
  const sender = startFrameSender(f.hub, f.video, f.opts);
  f.tick();
  f.tick();
  assert.equal(sender.sent(), 2);
  assert.deepEqual(f.published[0], { topic: TOPIC, data: { jpeg: "ZnJhbWU=", w: 640, h: 360 } });
  assert.equal(f.canvas.width, 640);
  assert.deepEqual(f.draws[0].slice(1), [0, 0, 640, 360]);
  sender.stop();
  assert.ok(f.wasCleared());
});

test("waits until the video has a frame", () => {
  const f = fakes({ ready: 1 });
  const sender = startFrameSender(f.hub, f.video, f.opts);
  f.tick();
  assert.equal(sender.sent(), 0);
  f.video.readyState = 4;
  f.tick();
  assert.equal(sender.sent(), 1);
});
