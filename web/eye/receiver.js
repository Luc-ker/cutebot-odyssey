// Laptop WebRTC receiver for the phone stream (T26, whitepaper §7.2).
// C9: `await receivePhoneStream(hub) -> MediaStream`, plus `onStream(cb)` for later streams.
// The eye answers; the phone (T25) offers. Signalling on `webrtc.signal` (C3).
//
// LAN only, so no ICE servers. To cross networks, pass e.g.
//   { iceServers: [{ urls: "stun:stun.l.google.com:19302" },
//                  { urls: "turn:turn.example.org:3478", username: "u", credential: "p" }] }
// to `new RTCPeerConnection(...)` below (and the same on the phone side).

export const SIGNAL = "webrtc.signal";
const ME = "eye";
const PEER = "phone";
const DISCONNECT_GRACE_MS = 3000;
const HELLO_RETRY_MS = 5000; // while nothing is connected, keep asking the phone for an offer

const listeners = new Set();
const receivers = new WeakMap();

/** Register a callback for every new phone stream (initial and after reconnects). */
export function onStream(cb) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/** Resolve with the current phone stream, or the next one to arrive. */
export function receivePhoneStream(hub, deps = {}) {
  let r = receivers.get(hub);
  if (!r) {
    r = createReceiver(hub, deps);
    receivers.set(hub, r);
    r.start();
  }
  return r.stream();
}

/**
 * The receiver itself, exported for tests.
 * @returns {{start(): void, stream(): Promise<MediaStream>, close(): void, readonly pc: any}}
 */
export function createReceiver(hub, {
  RTCPeerConnection = globalThis.RTCPeerConnection,
  MediaStream = globalThis.MediaStream,
  setTimeout: setT = globalThis.setTimeout.bind(globalThis),
  clearTimeout: clearT = globalThis.clearTimeout.bind(globalThis),
} = {}) {
  let pc = null;
  let current = null; // latest MediaStream
  let waiters = [];
  let pendingCandidates = [];
  let helloTimer = null;
  let graceTimer = null;
  let closed = false;

  const send = (msg) => hub.pub(SIGNAL, { to: PEER, from: ME, ...msg });

  function hello() {
    if (closed) return;
    send({ sdp: null });
    if (helloTimer) clearT(helloTimer);
    helloTimer = setT(() => {
      helloTimer = null;
      if (!pc || pc.connectionState !== "connected") hello();
    }, HELLO_RETRY_MS);
  }

  function deliver(stream) {
    if (stream === current) return;
    current = stream;
    const w = waiters;
    waiters = [];
    w.forEach((resolve) => resolve(stream));
    listeners.forEach((cb) => { try { cb(stream); } catch (e) { console.error(e); } });
  }

  function closePc() {
    if (!pc) return;
    const old = pc;
    pc = null;
    old.ontrack = old.onicecandidate = old.onconnectionstatechange = null;
    try { old.close(); } catch { /* ignore */ }
  }

  async function answer(offer) {
    // Keep pendingCandidates: anything queued arrived before this offer settled and belongs to it.
    // Candidates for an older session went straight to the old pc, so they never sit in the queue.
    closePc();
    const conn = new RTCPeerConnection({ iceServers: [] });
    pc = conn;

    let gathered = null;
    conn.ontrack = (e) => {
      if (pc !== conn) return;
      let stream = e.streams?.[0];
      if (!stream) {
        gathered ??= new MediaStream();
        gathered.addTrack(e.track);
        stream = gathered;
      }
      deliver(stream);
    };
    conn.onicecandidate = (e) => {
      if (pc === conn && e.candidate) {
        send({ candidate: e.candidate.toJSON ? e.candidate.toJSON() : e.candidate });
      }
    };
    conn.onconnectionstatechange = () => {
      if (pc !== conn) return;
      const s = conn.connectionState;
      if (s === "connected") {
        if (graceTimer) { clearT(graceTimer); graceTimer = null; }
        if (helloTimer) { clearT(helloTimer); helloTimer = null; }
      } else if (s === "failed" || s === "closed") {
        hello();
      } else if (s === "disconnected") {
        if (graceTimer) clearT(graceTimer);
        graceTimer = setT(() => {
          graceTimer = null;
          if (pc === conn && conn.connectionState !== "connected") hello();
        }, DISCONNECT_GRACE_MS);
      }
    };

    await conn.setRemoteDescription(offer);
    if (pc !== conn) return;
    const queued = pendingCandidates;
    pendingCandidates = [];
    for (const c of queued) await conn.addIceCandidate(c).catch(() => {});
    const desc = await conn.createAnswer();
    if (pc !== conn) return;
    await conn.setLocalDescription(desc);
    if (pc !== conn) return;
    const local = conn.localDescription ?? desc;
    send({ sdp: { type: local.type, sdp: local.sdp } });
  }

  async function onSignal(env) {
    const msg = env?.data;
    if (!msg || msg.to !== ME || closed) return;
    try {
      if (msg.sdp?.type === "offer") {
        await answer(msg.sdp);
      } else if (msg.candidate) {
        if (!pc || !pc.remoteDescription) pendingCandidates.push(msg.candidate);
        else await pc.addIceCandidate(msg.candidate).catch(() => {});
      }
    } catch (err) {
      console.warn("[eye receiver] signalling error", err);
      hello();
    }
  }

  return {
    start() {
      hub.sub(SIGNAL, onSignal);
      hello();
    },
    stream() {
      return current ? Promise.resolve(current) : new Promise((r) => waiters.push(r));
    },
    close() {
      closed = true;
      if (helloTimer) clearT(helloTimer);
      if (graceTimer) clearT(graceTimer);
      closePc();
    },
    get pc() { return pc; },
    _onSignal: onSignal,
  };
}
