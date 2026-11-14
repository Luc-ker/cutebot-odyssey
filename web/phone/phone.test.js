// node --test web/phone/phone.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createPhoneStreamer, SIGNAL } from "./phone.js";

class FakePC {
  static all = [];
  constructor(cfg) {
    this.cfg = cfg;
    this.tracks = [];
    this.connectionState = "new";
    this.signalingState = "stable";
    this.localDescription = null;
    this.remoteDescription = null;
    this.candidates = [];
    this.closed = false;
    FakePC.all.push(this);
  }
  addTrack(t) { this.tracks.push(t); }
  async createOffer() { return { type: "offer", sdp: `offer-${FakePC.all.indexOf(this)}` }; }
  async setLocalDescription(d) { this.localDescription = d; this.signalingState = "have-local-offer"; }
  async setRemoteDescription(d) { this.remoteDescription = d; this.signalingState = "stable"; }
  async addIceCandidate(c) { this.candidates.push(c); }
  close() { this.closed = true; this.connectionState = "closed"; }
  setState(s) { this.connectionState = s; this.onconnectionstatechange?.(); }
}

function fakeHub() {
  const subs = [];
  return {
    published: [],
    sub(pattern, cb) { subs.push([pattern, cb]); },
    pub(topic, data) { this.published.push({ topic, data }); },
    async emit(topic, data) {
      for (const [p, cb] of subs) if (p === topic) await cb({ topic, ts: 0, src: "test", data });
    },
  };
}

const track = { stop() { this.stopped = true; } };
const stream = { getTracks: () => [track] };
const timers = { setTimeout: () => 0, clearTimeout: () => {} };
const offers = (hub) => hub.published.filter((m) => m.topic === SIGNAL && m.data.sdp?.type === "offer");

async function started() {
  FakePC.all = [];
  const hub = fakeHub();
  const states = [];
  const s = createPhoneStreamer({
    hub, getStream: async () => stream, RTCPeerConnection: FakePC, onState: (x) => states.push(x), ...timers,
  });
  await s.start();
  return { hub, s, states };
}

test("start sends an offer to the eye with the camera tracks", async () => {
  const { hub } = await started();
  const sent = offers(hub);
  assert.equal(sent.length, 1);
  assert.deepEqual(sent[0].data, { to: "eye", from: "phone", sdp: { type: "offer", sdp: "offer-0" } });
  assert.deepEqual(FakePC.all[0].tracks, [track]);
  assert.deepEqual(FakePC.all[0].cfg, { iceServers: [] });
});

test("an incoming hello triggers a new offer on a fresh peer connection", async () => {
  const { hub } = await started();
  await hub.emit(SIGNAL, { to: "phone", from: "eye", sdp: null });
  assert.equal(offers(hub).length, 2);
  assert.equal(FakePC.all.length, 2);
  assert.equal(FakePC.all[0].closed, true);
  assert.equal(offers(hub)[1].data.sdp.sdp, "offer-1");
});

test("hello addressed to someone else is ignored", async () => {
  const { hub } = await started();
  await hub.emit(SIGNAL, { to: "eye", from: "phone", sdp: null });
  assert.equal(offers(hub).length, 1);
});

test("answer is applied and early candidates are flushed after it", async () => {
  const { hub } = await started();
  const pc = FakePC.all[0];
  await hub.emit(SIGNAL, { to: "phone", from: "eye", candidate: { candidate: "c1" } });
  assert.deepEqual(pc.candidates, []);
  await hub.emit(SIGNAL, { to: "phone", from: "eye", sdp: { type: "answer", sdp: "a" } });
  assert.deepEqual(pc.remoteDescription, { type: "answer", sdp: "a" });
  assert.deepEqual(pc.candidates, [{ candidate: "c1" }]);
  await hub.emit(SIGNAL, { to: "phone", from: "eye", candidate: { candidate: "c2" } });
  assert.deepEqual(pc.candidates.map((c) => c.candidate), ["c1", "c2"]);
});

test("local ICE candidates are sent to the eye", async () => {
  const { hub } = await started();
  FakePC.all[0].onicecandidate({ candidate: { toJSON: () => ({ candidate: "x", sdpMid: "0" }) } });
  const last = hub.published.at(-1).data;
  assert.deepEqual(last, { to: "eye", from: "phone", candidate: { candidate: "x", sdpMid: "0" } });
});

test("a failed connection restarts with a new offer", async () => {
  const { hub, states } = await started();
  FakePC.all[0].setState("failed");
  await new Promise((r) => setImmediate(r));
  assert.equal(offers(hub).length, 2);
  assert.ok(states.includes("reconnecting"));
});

test("connected reports streaming", async () => {
  const { states } = await started();
  FakePC.all[0].setState("connected");
  assert.equal(states.at(-1), "streaming");
});
