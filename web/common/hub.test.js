import test from "node:test";
import assert from "node:assert/strict";
import { createHub, connectHub, defaultHubUrl, topicMatches } from "./hub.js";

// A controllable fake WebSocket. Every instance is recorded so tests can open/close/feed it.
function makeFakeWs() {
  const sockets = [];
  class FakeWs {
    constructor(url) {
      this.url = url;
      this.sent = [];
      this.closed = false;
      sockets.push(this);
    }
    send(text) {
      this.sent.push(JSON.parse(text));
    }
    close() {
      this.closed = true;
    }
    // test helpers
    open() {
      this.onopen?.();
    }
    drop() {
      this.onclose?.();
    }
    deliver(env) {
      this.onmessage?.({ data: JSON.stringify(env) });
    }
  }
  return { FakeWs, sockets };
}

// Timers run only when the test says so; delays are recorded to check backoff.
function makeTimers() {
  const queue = [];
  const delays = [];
  return {
    setTimeout(fn, ms) {
      delays.push(ms);
      queue.push(fn);
    },
    runAll() {
      while (queue.length) queue.shift()();
    },
    delays,
  };
}

const env = (topic, data = {}) => ({ topic, ts: 1, src: "t", data });

test("connectHub resolves once open; pub sends an envelope", async () => {
  const { FakeWs, sockets } = makeFakeWs();
  const p = connectHub("ws://h/hub", "map", { WebSocket: FakeWs, now: () => 42 });
  sockets[0].open();
  const hub = await p;
  assert.equal(hub.isOpen, true);
  assert.equal(hub.pub("narration.say", { text: "hi", priority: 1 }), true);
  assert.deepEqual(sockets[0].sent.at(-1), {
    op: "pub", topic: "narration.say", ts: 42, src: "map", data: { text: "hi", priority: 1 },
  });
});

test("vision.* fires for vision.state, not for world.current", () => {
  const { FakeWs, sockets } = makeFakeWs();
  const hub = createHub("ws://h/hub", "t", { WebSocket: FakeWs });
  const got = [];
  hub.sub("vision.*", (e) => got.push(e.topic));
  sockets[0].open();
  assert.deepEqual(sockets[0].sent, [{ op: "sub", topics: ["vision.*"] }]);
  sockets[0].deliver(env("vision.state"));
  sockets[0].deliver(env("world.current"));
  assert.deepEqual(got, ["vision.state"]);
});

test("subscriptions are re-sent after a reconnect, with backoff", () => {
  const { FakeWs, sockets } = makeFakeWs();
  const timers = makeTimers();
  const statuses = [];
  const hub = createHub("ws://h/hub", "t", { WebSocket: FakeWs, setTimeout: timers.setTimeout });
  hub.onStatus((s) => statuses.push(s));
  sockets[0].open();
  hub.sub("vision.*", () => {});
  hub.sub("audio.beat", () => {});
  sockets[0].drop();
  timers.runAll(); // reconnect attempt 1 fails
  sockets[1].drop();
  timers.runAll(); // attempt 2 fails
  sockets[2].drop();
  timers.runAll(); // attempt 3 succeeds
  sockets[3].open();
  assert.deepEqual(sockets[3].sent, [{ op: "sub", topics: ["vision.*", "audio.beat"] }]);
  assert.deepEqual(timers.delays, [500, 1000, 2000]);
  assert.deepEqual(statuses, ["open", "closed", "open"]);
  sockets[3].drop();
  timers.runAll();
  assert.equal(timers.delays.at(-1), 500, "backoff resets after a successful open");
});

test("backoff caps at 5 s", () => {
  const { FakeWs, sockets } = makeFakeWs();
  const timers = makeTimers();
  createHub("ws://h/hub", "t", { WebSocket: FakeWs, setTimeout: timers.setTimeout });
  for (let i = 0; i < 8; i++) {
    sockets.at(-1).drop();
    timers.runAll();
  }
  assert.deepEqual(timers.delays, [500, 1000, 2000, 4000, 5000, 5000, 5000, 5000]);
});

test("messages published while disconnected are dropped, except the last webrtc.signal", () => {
  const { FakeWs, sockets } = makeFakeWs();
  const timers = makeTimers();
  const hub = createHub("ws://h/hub", "phone", { WebSocket: FakeWs, setTimeout: timers.setTimeout });
  assert.equal(hub.pub("audio.beat", { tempo_bpm: 1, strength: 1 }), false);
  hub.pub("webrtc.signal", { to: "eye", from: "phone", sdp: "a" });
  hub.pub("webrtc.signal", { to: "eye", from: "phone", sdp: "b" });
  sockets[0].open();
  const pubs = sockets[0].sent.filter((m) => m.op === "pub");
  assert.equal(pubs.length, 1);
  assert.equal(pubs[0].topic, "webrtc.signal");
  assert.equal(pubs[0].data.sdp, "b");
  sockets[0].drop();
  timers.runAll();
  sockets[1].open();
  assert.equal(sockets[1].sent.filter((m) => m.op === "pub").length, 0, "retried only once");
});

test("a throwing callback does not stop other callbacks; unsubscribe works", () => {
  const { FakeWs, sockets } = makeFakeWs();
  const hub = createHub("ws://h/hub", "t", { WebSocket: FakeWs });
  const got = [];
  const origError = console.error;
  console.error = () => {};
  try {
    hub.sub("world.*", () => {
      throw new Error("boom");
    });
    const off = hub.sub("world.*", (e) => got.push(e.topic));
    sockets[0].open();
    sockets[0].deliver(env("world.event"));
    off();
    sockets[0].deliver(env("world.event"));
  } finally {
    console.error = origError;
  }
  assert.deepEqual(got, ["world.event"]);
});

test("close() stops reconnecting", () => {
  const { FakeWs, sockets } = makeFakeWs();
  const timers = makeTimers();
  const hub = createHub("ws://h/hub", "t", { WebSocket: FakeWs, setTimeout: timers.setTimeout });
  sockets[0].open();
  hub.close();
  sockets[0].drop();
  timers.runAll();
  assert.equal(sockets.length, 1);
});

test("default URL matches the page scheme", () => {
  assert.equal(defaultHubUrl({ protocol: "https:", host: "10.0.0.2:8765" }), "wss://10.0.0.2:8765/hub");
  assert.equal(defaultHubUrl({ protocol: "http:", host: "localhost:8765" }), "ws://localhost:8765/hub");
  assert.ok(topicMatches("*", "x"));
});
