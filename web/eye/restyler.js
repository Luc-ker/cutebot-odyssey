// Restyler adapter (T28, whitepaper §7.2, §7.15).
// C9: createRestyler(config) -> {start(stream) -> Promise<MediaStream>, setPrompt(text), stop(), onStatus(cb)}
// Status: {ok, fps, latency_ms}. ok:false when no output frame has arrived for 1.5 s.
//
// Switching provider is this one line (or set RESTYLE_PROVIDER in config):
export const PROVIDER = "fake"; // "fake" | "decart"
//
// Provider keys never live in the repo: they come from sessionStorage, or a prompt on the page.

const STALL_MS = 1500;
const CHECK_MS = 250;
const STATUS_EVERY_MS = 500;

// Decart realtime SDK (see docs/restyle-provider.md). Pin a version once the spike settles it.
const DECART_SDK_URL = "https://esm.sh/@decartai/sdk";
const DECART_MODEL = "lucy-restyle-2";

// ---------------------------------------------------------------------------------------------
// Fake provider: tints the raw feed by prompt keywords. For development, tests, and offline use.

const KEYWORD_TINTS = [
  [["ocean", "sea", "water", "storm", "wave", "harbour", "reef"], [20, 110, 150]],
  [["lava", "volcan", "fire", "ember", "inferno", "ash", "wasteland"], [210, 70, 20]],
  [["snow", "ice", "frost", "winter", "glacier", "lullaby"], [170, 205, 240]],
  [["jungle", "forest", "grove", "swamp", "moss"], [40, 140, 60]],
  [["neon", "cyber", "city", "synth"], [200, 40, 200]],
  [["desert", "sand", "dune"], [215, 170, 90]],
  [["kingdom", "castle", "gold", "royal", "sunny"], [220, 175, 60]],
];
const DARK_WORDS = ["night", "dusk", "dark", "midnight", "shadow", "moon"];

/** Pure: prompt text -> {rgb, strength, dark}. Exported for tests and the fallback overlay. */
export function tintForPrompt(text = "") {
  const t = String(text).toLowerCase();
  const hits = KEYWORD_TINTS.filter(([words]) => words.some((w) => t.includes(w))).map(([, rgb]) => rgb);
  const dark = DARK_WORDS.some((w) => t.includes(w));
  if (!hits.length) return { rgb: [128, 128, 128], strength: 0, dark };
  const rgb = [0, 1, 2].map((i) => Math.round(hits.reduce((s, c) => s + c[i], 0) / hits.length));
  return { rgb, strength: 0.45, dark };
}

/** Browser surface: plays the input in a hidden <video>, draws tinted frames into a canvas. */
function canvasSurface() {
  let video, canvas, raf, vfc, running = false;
  return {
    async start(stream, onFrame, getTint) {
      video = Object.assign(document.createElement("video"), { muted: true, playsInline: true, srcObject: stream });
      await video.play().catch(() => {});
      canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      running = true;
      let lastTime = -1;
      const draw = () => {
        if (!running) return;
        const w = video.videoWidth, h = video.videoHeight;
        // Only count a frame when the source actually produced a new one, so a stalled phone
        // feed shows up as ok:false instead of a frozen picture that looks healthy.
        if (w && h && video.currentTime !== lastTime) {
          lastTime = video.currentTime;
          if (canvas.width !== w) { canvas.width = w; canvas.height = h; }
          const { rgb, strength, dark } = getTint();
          ctx.filter = `saturate(1.25) contrast(1.1)${dark ? " brightness(0.7)" : ""}`;
          ctx.drawImage(video, 0, 0, w, h);
          ctx.filter = "none";
          if (strength > 0) {
            ctx.globalCompositeOperation = "color";
            ctx.globalAlpha = strength;
            ctx.fillStyle = `rgb(${rgb.join(",")})`;
            ctx.fillRect(0, 0, w, h);
            ctx.globalCompositeOperation = "source-over";
            ctx.globalAlpha = 1;
          }
          onFrame();
        }
        schedule();
      };
      const schedule = () => {
        if (video.requestVideoFrameCallback) vfc = video.requestVideoFrameCallback(draw);
        else raf = requestAnimationFrame(draw);
      };
      schedule();
      return canvas.captureStream(30);
    },
    stop() {
      running = false;
      if (raf) cancelAnimationFrame(raf);
      if (vfc && video?.cancelVideoFrameCallback) video.cancelVideoFrameCallback(vfc);
      if (video) video.srcObject = null;
    },
  };
}

function fakeProvider(config, deps, emitFrame) {
  let tint = tintForPrompt("");
  const surface = (deps.makeSurface ?? canvasSurface)();
  return {
    name: "fake",
    start: (stream) => surface.start(stream, () => emitFrame(0), () => tint),
    setPrompt(text) { tint = tintForPrompt(text); },
    stop: () => surface.stop(),
    get tint() { return tint; },
  };
}

// ---------------------------------------------------------------------------------------------
// Decart realtime restyling (WebRTC). API per docs.platform.decart.ai, read 2026-11.

function readKey(provider, deps) {
  const storage = deps.sessionStorage ?? globalThis.sessionStorage;
  const slot = `genrator.restyle.key.${provider}`;
  let key = null;
  try { key = storage?.getItem(slot); } catch { /* storage blocked */ }
  if (!key && typeof globalThis.prompt === "function") {
    key = globalThis.prompt(`API key for ${provider} (kept in this tab only):`) || null;
    try { if (key) storage?.setItem(slot, key); } catch { /* ignore */ }
  }
  if (!key) throw new Error(`no ${provider} API key`);
  return key;
}

/** Calls onFrame for every frame the stream renders (used to watch remote providers). */
function watchFrames(stream, onFrame) {
  const v = Object.assign(document.createElement("video"), { muted: true, playsInline: true, srcObject: stream });
  let on = true;
  let lastTime = -1;
  const step = () => {
    if (!on) return;
    if (v.currentTime !== lastTime) { lastTime = v.currentTime; onFrame(); }
    v.requestVideoFrameCallback ? v.requestVideoFrameCallback(step) : requestAnimationFrame(step);
  };
  v.play().catch(() => {}).finally(step);
  return () => { on = false; v.srcObject = null; };
}

function decartProvider(config, deps, emitFrame) {
  let client = null, unwatch = null, prompt = "", latency = null;
  return {
    name: "decart",
    async start(stream) {
      const apiKey = readKey("decart", deps);
      const { createDecartClient, models } = await import(DECART_SDK_URL);
      const decart = createDecartClient({ apiKey, telemetry: false });
      let resolveOut;
      const out = new Promise((r) => { resolveOut = r; });
      client = await decart.realtime.connect(stream, {
        model: models.realtime(config.DECART_MODEL ?? DECART_MODEL),
        onRemoteStream: (remote) => {
          unwatch?.();
          unwatch = watchFrames(remote, () => emitFrame(latency));
          resolveOut(remote);
        },
        // enhance:false keeps our composed prompts literal, so the style stays predictable.
        initialState: { prompt: { text: prompt || "a painterly fantasy world", enhance: false } },
      });
      client.on?.("stats", (s) => {
        const ms = s?.latency?.medianMs ?? s?.medianMs ?? s?.glassToGlass?.medianMs;
        if (Number.isFinite(ms)) latency = Math.round(ms);
      });
      client.on?.("error", (e) => console.warn("[restyler/decart]", e?.code, e?.message));
      return out;
    },
    setPrompt(text) {
      prompt = text;
      if (client) Promise.resolve(client.setPrompt(text, { enhance: false })).catch((e) => console.warn("[restyler/decart] setPrompt", e));
    },
    stop() {
      unwatch?.();
      try { client?.disconnect(); } catch { /* ignore */ }
      client = null;
    },
  };
}

export const PROVIDERS = { fake: fakeProvider, decart: decartProvider };

// ---------------------------------------------------------------------------------------------

/**
 * @param {object} config  shared config (C10); RESTYLE_PROVIDER overrides PROVIDER
 * @param {object} [deps]  test seams: now, setInterval, clearInterval, makeSurface, sessionStorage
 */
export function createRestyler(config = {}, deps = {}) {
  const now = deps.now ?? (() => performance.now());
  const setI = deps.setInterval ?? globalThis.setInterval.bind(globalThis);
  const clearI = deps.clearInterval ?? globalThis.clearInterval.bind(globalThis);

  const name = config.RESTYLE_PROVIDER ?? PROVIDER;
  const factory = PROVIDERS[name];
  if (!factory) throw new Error(`unknown restyle provider "${name}"`);

  const listeners = new Set();
  let frames = []; // recent frame times, for fps
  let lastFrame = -Infinity;
  let latency = null;
  let ok = false;
  let lastEmit = -Infinity;
  let timer = null;
  let prompt = null;

  const status = () => ({ ok, fps: frames.length, latency_ms: latency });
  const emit = () => {
    lastEmit = now();
    const s = status();
    listeners.forEach((cb) => { try { cb(s); } catch (e) { console.error(e); } });
  };

  const provider = factory(config, deps, (latencyMs) => {
    const t = now();
    lastFrame = t;
    frames.push(t);
    if (Number.isFinite(latencyMs)) latency = latencyMs;
    if (!ok) { ok = true; emit(); }
  });

  const check = () => {
    const t = now();
    frames = frames.filter((f) => t - f <= 1000);
    const fresh = t - lastFrame < STALL_MS;
    if (fresh !== ok) { ok = fresh; emit(); }
    else if (t - lastEmit >= STATUS_EVERY_MS) emit();
  };

  const api = {
    provider,
    async start(stream) {
      api.stop();
      // ok only once a real frame arrives; the fallback (T33) debounces the switch to raw.
      lastFrame = -Infinity;
      ok = false;
      timer = setI(check, CHECK_MS);
      try {
        if (prompt !== null) provider.setPrompt(prompt);
        return await provider.start(stream);
      } catch (err) {
        lastFrame = -Infinity;
        ok = false;
        emit();
        throw err;
      }
    },
    setPrompt(text) {
      prompt = String(text ?? "");
      provider.setPrompt(prompt);
    },
    stop() {
      if (timer) { clearI(timer); timer = null; }
      provider.stop();
      if (ok) { ok = false; emit(); }
    },
    onStatus(cb) {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    get status() { return status(); },
  };
  return api;
}
