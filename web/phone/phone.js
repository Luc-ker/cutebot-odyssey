// Phone camera streaming page (T25, whitepaper §7.2, §5).
// Streams the rear camera to the eye page (T26) over WebRTC, signalling through the hub on
// `webrtc.signal` (C3): {to, from, sdp?, candidate?}. The phone always makes the offer; the eye
// answers. A {to:"phone", sdp:null} "hello" from the eye means "start again", so an eye reload
// recovers without touching the phone.

export const SIGNAL = "webrtc.signal";
export const ME = "phone";
export const PEER = "eye";

export const VIDEO_CONSTRAINTS = {
  audio: false,
  video: {
    facingMode: { ideal: "environment" },
    aspectRatio: { ideal: 16 / 9 },
    width: { ideal: 960 },
    height: { ideal: 540 },
    frameRate: { ideal: 30, max: 30 },
  },
};

const DISCONNECT_GRACE_MS = 3000; // "disconnected" often heals by itself
const ANSWER_TIMEOUT_MS = 8000; // no answer: offer again (eye may have been off)

/**
 * Core streamer, free of page DOM so it can be tested with fakes.
 * @param {object} o
 * @param {{pub: Function, sub: Function}} o.hub         hub client (C2)
 * @param {() => Promise<MediaStream>} o.getStream      camera source
 * @param {typeof RTCPeerConnection} o.RTCPeerConnection
 * @param {(s: string) => void} [o.onState]             "starting" | "offering" | "streaming" | "reconnecting" | "error"
 */
export function createPhoneStreamer({
  hub,
  getStream,
  RTCPeerConnection = globalThis.RTCPeerConnection,
  onState = () => {},
  setTimeout: setT = globalThis.setTimeout.bind(globalThis),
  clearTimeout: clearT = globalThis.clearTimeout.bind(globalThis),
}) {
  let stream = null;
  let pc = null;
  let pendingCandidates = [];
  let timer = null;
  let stopped = false;

  const send = (msg) => hub.pub(SIGNAL, { to: PEER, from: ME, ...msg });
  const plain = (d) => (d ? { type: d.type, sdp: d.sdp } : null);

  function schedule(ms, fn) {
    if (timer) clearT(timer);
    timer = setT(() => { timer = null; fn(); }, ms);
  }

  function closePc() {
    if (!pc) return;
    const old = pc;
    pc = null;
    old.onicecandidate = old.onconnectionstatechange = null;
    try { old.close(); } catch { /* already closed */ }
  }

  async function offer() {
    if (stopped) return;
    closePc();
    pendingCandidates = [];
    // LAN only: no STUN/TURN. Add {iceServers: [{urls: "stun:..."}]} here to cross networks.
    const conn = new RTCPeerConnection({ iceServers: [] });
    pc = conn;
    for (const track of stream.getTracks()) conn.addTrack(track, stream);

    conn.onicecandidate = (e) => {
      if (pc === conn && e.candidate) {
        send({ candidate: e.candidate.toJSON ? e.candidate.toJSON() : e.candidate });
      }
    };
    conn.onconnectionstatechange = () => {
      if (pc !== conn) return;
      const s = conn.connectionState;
      if (s === "connected") {
        if (timer) { clearT(timer); timer = null; }
        onState("streaming");
      } else if (s === "failed" || s === "closed") {
        onState("reconnecting");
        offer();
      } else if (s === "disconnected") {
        onState("reconnecting");
        schedule(DISCONNECT_GRACE_MS, () => {
          if (pc === conn && conn.connectionState !== "connected") offer();
        });
      }
    };

    onState("offering");
    const desc = await conn.createOffer();
    if (pc !== conn) return; // superseded while awaiting
    await conn.setLocalDescription(desc);
    if (pc !== conn) return;
    send({ sdp: plain(conn.localDescription ?? desc) });
    schedule(ANSWER_TIMEOUT_MS, () => {
      if (pc === conn && conn.connectionState !== "connected") offer();
    });
  }

  async function onSignal(env) {
    const msg = env?.data;
    if (!msg || msg.to !== ME || stopped) return;
    try {
      if ("sdp" in msg && msg.sdp === null && !msg.candidate) {
        // "hello": the eye (re)started and wants a fresh offer.
        await offer();
      } else if (msg.sdp?.type === "answer") {
        if (!pc || pc.signalingState !== "have-local-offer") return; // stale answer
        await pc.setRemoteDescription(msg.sdp);
        const queued = pendingCandidates;
        pendingCandidates = [];
        for (const c of queued) await pc.addIceCandidate(c).catch(() => {});
      } else if (msg.candidate) {
        if (!pc) return;
        if (!pc.remoteDescription) pendingCandidates.push(msg.candidate);
        else await pc.addIceCandidate(msg.candidate).catch(() => {});
      }
    } catch (err) {
      console.warn("[phone] signalling error", err);
      onState("error");
    }
  }

  return {
    async start() {
      onState("starting");
      stream = await getStream();
      hub.sub(SIGNAL, onSignal);
      await offer();
      return stream;
    },
    stop() {
      stopped = true;
      if (timer) clearT(timer);
      closePc();
      stream?.getTracks().forEach((t) => t.stop());
    },
    /** For tests and the page indicator. */
    get pc() { return pc; },
    _onSignal: onSignal,
  };
}

// ---------------------------------------------------------------------------------------------
// Page wiring (only runs in the browser, from index.html).

const LABELS = {
  starting: "Starting camera…",
  offering: "Waiting for the eye screen…",
  streaming: "STREAMING",
  reconnecting: "Reconnecting…",
  error: "Error, retrying…",
};

// iPhone Safari may reject or omit orientation locking. Camera streaming must still start.
async function preferLandscape() {
  try { await globalThis.screen?.orientation?.lock?.("landscape"); } catch { /* use the rotation hint */ }
}

async function keepAwake(statusEl) {
  if (!("wakeLock" in navigator)) {
    statusEl.textContent = "Screen lock: keep the screen on manually";
    return;
  }
  let lock = null;
  const acquire = async () => {
    try {
      lock = await navigator.wakeLock.request("screen");
      statusEl.textContent = "Screen kept awake";
      lock.addEventListener("release", () => { statusEl.textContent = "Screen lock released"; });
    } catch (e) {
      statusEl.textContent = `Wake lock failed: ${e.message}`;
    }
  };
  // The lock is dropped whenever the page is hidden; take it again on return.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && (!lock || lock.released)) acquire();
  });
  await acquire();
}

async function showBattery(el) {
  if (!navigator.getBattery) { el.textContent = "Battery: n/a"; return; }
  const b = await navigator.getBattery();
  const draw = () => {
    const pct = Math.round(b.level * 100);
    el.textContent = `Battery ${pct}%${b.charging ? " ⚡" : ""}`;
    el.classList.toggle("low", pct <= 20 && !b.charging);
  };
  b.addEventListener("levelchange", draw);
  b.addEventListener("chargingchange", draw);
  draw();
}

export async function main() {
  const $ = (id) => document.getElementById(id);
  const indicator = $("indicator");
  const preview = $("preview");

  if (!window.isSecureContext) {
    indicator.textContent = "Needs HTTPS: open this page via https://";
    indicator.dataset.state = "error";
    return;
  }

  preferLandscape();
  showBattery($("battery")).catch(() => {});

  const { connectHub } = await import("../common/hub.js");
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const hub = await connectHub(`${proto}//${location.host}/hub`, "phone");
  hub.onStatus?.((s) => { $("hub").textContent = s === "open" ? "Hub connected" : "Hub offline"; });
  $("hub").textContent = "Hub connected";

  const streamer = createPhoneStreamer({
    hub,
    getStream: () => navigator.mediaDevices.getUserMedia(VIDEO_CONSTRAINTS),
    onState: (s) => {
      indicator.textContent = LABELS[s] ?? s;
      indicator.dataset.state = s;
    },
  });

  // Wake Lock needs a user gesture on some browsers; try now, and again on first tap.
  keepAwake($("wake"));
  document.addEventListener("click", () => {
    preferLandscape();
    keepAwake($("wake"));
  }, { once: true });

  try {
    preview.srcObject = await streamer.start();
    const s = preview.srcObject.getVideoTracks()[0]?.getSettings?.() ?? {};
    $("res").textContent = s.width ? `${s.width}×${s.height} @ ${Math.round(s.frameRate ?? 0)} fps` : "";
  } catch (e) {
    indicator.textContent = `Camera error: ${e.message}`;
    indicator.dataset.state = "error";
  }
}
