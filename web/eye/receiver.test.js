// node --test web/eye/receiver.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createReceiver, receivePhoneStream, onStream, SIGNAL } from "./receiver.js";

class FakePC {
  static all = [];
  constructor(cfg) {
    this.cfg = cfg;
    this.connectionState = "new";
    this.remoteDescription = null;
    this.localDescription = null;
    this.candidates = [];
    this.closed = false;
    FakePC.all.push(this);
  }
  async setRemoteDescription(d) { this.remoteDescription = d; }
  async createAnswer() { return { type: "answer", sdp: `answer-${FakePC.all.indexOf(this)}` }; }
  async setLocalDescription(d) { this.localDescription = d; }
  async addIceCandidate(c) { this.candidates.push(c); }
  close() { this.closed = true; }
  setState(s) { this.connectionState = s; this.onconnectionstatechange?.(); }
}

function fakeHub() {
  const subs = [];
  return {
    published: [],
    sub(p, cb) { subs.push([p, cb]); },
    pub(topic, data) { this.published.push({ topic, data }); },
    async emit(topic, data) { for (const [p, cb] of subs) if (p === topic) await cb({ topic, data }); },
  };
}

const deps = { RTCPeerConnection: FakePC, setTimeout: () => 0, clearTimeout: () => {} };
const offer = (n) => ({ to: "eye", from: "phone", sdp: { type: "offer", sdp: `offer-${n}` } });
const hellos = (hub) => hub.published.filter((m) => m.data.sdp === null);

test("start publishes a hello to the phone", () => {
  FakePC.all = [];
  const hub = fakeHub();
  createReceiver(hub, deps).start();
  assert.deepEqual(hub.published, [{ topic: SIGNAL, data: { to: "phone", from: "eye", sdp: null } }]);
});

test("offer in -> answer published with to:'phone'", async () => {
  FakePC.all = [];
  const hub = fakeHub();
  createReceiver(hub, deps).start();
  await hub.emit(SIGNAL, offer(0));
  const answer = hub.published.find((m) => m.data.sdp?.type === "answer");
  assert.deepEqual(answer.data, { to: "phone", from: "eye", sdp: { type: "answer", sdp: "answer-0" } });
  assert.deepEqual(FakePC.all[0].remoteDescription, { type: "offer", sdp: "offer-0" });
  assert.deepEqual(FakePC.all[0].cfg, { iceServers: [] });
});

test("resolves with the remote stream and notifies onStream", async () => {
  FakePC.all = [];
  const hub = fakeHub();
  const seen = [];
  const off = onStream((s) => seen.push(s));
  const pending = receivePhoneStream(hub, deps);
  await hub.emit(SIGNAL, offer(0));
  const remote = { id: "remote-1" };
  FakePC.all[0].ontrack({ streams: [remote], track: {} });
  assert.equal(await pending, remote);
  assert.equal(await receivePhoneStream(hub, deps), remote); // same hub reuses the receiver
  assert.deepEqual(seen, [remote]);
  off();
});

test("candidates before the offer settles are queued, later ones applied", async () => {
  FakePC.all = [];
  const hub = fakeHub();
  createReceiver(hub, deps).start();
  await hub.emit(SIGNAL, { to: "eye", from: "phone", candidate: { candidate: "early" } });
  await hub.emit(SIGNAL, offer(0));
  await hub.emit(SIGNAL, { to: "eye", from: "phone", candidate: { candidate: "late" } });
  assert.deepEqual(FakePC.all[0].candidates.map((c) => c.candidate), ["early", "late"]);
});

test("disconnect: hello again and the next stream replaces the old one", async () => {
  FakePC.all = [];
  const hub = fakeHub();
  const r = createReceiver(hub, deps);
  r.start();
  await hub.emit(SIGNAL, offer(0));
  FakePC.all[0].ontrack({ streams: [{ id: "s1" }] });
  FakePC.all[0].setState("failed");
  assert.equal(hellos(hub).length, 2);

  await hub.emit(SIGNAL, offer(1));
  assert.equal(FakePC.all[0].closed, true);
  FakePC.all[1].ontrack({ streams: [{ id: "s2" }] });
  assert.equal((await r.stream()).id, "s2");
});

test("messages for the phone are ignored", async () => {
  FakePC.all = [];
  const hub = fakeHub();
  createReceiver(hub, deps).start();
  await hub.emit(SIGNAL, { to: "phone", from: "eye", sdp: { type: "offer", sdp: "x" } });
  assert.equal(FakePC.all.length, 0);
});
