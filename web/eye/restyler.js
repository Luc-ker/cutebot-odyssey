// Restyler adapter (T28, whitepaper §7.2, §7.15).
// C9: createRestyler(config) -> {start(stream) -> Promise<MediaStream>, setPrompt(text), stop(), onStatus(cb)}
// Status: {ok, fps, latency_ms}. ok:false when no output frame has arrived for 1.5 s.
//
// Switching provider is this one line (or set RESTYLE_PROVIDER in config):
export const PROVIDER = "fake"; // "fake" | "decart"
//
// The permanent provider key stays on the hub; the browser requests short-lived tokens.

const STALL_MS = 1500;
const CHECK_MS = 250;
const STATUS_EVERY_MS = 500;

// Decart realtime SDK (see docs/restyle-provider.md). Pin a version once the spike settles it.
const DECART_SDK_URL = "https://esm.sh/@decartai/sdk@0.2.14";
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
function canvasSurface({ width, height, fps = 30, neutral = false } = {}) {
  let video, canvas, output, raf, vfc, running = false, generation = 0;
  return {
    async start(stream, onFrame, getTint) {
      const own = ++generation;
      video = Object.assign(document.createElement("video"), { muted: true, playsInline: true, srcObject: stream });
      await video.play().catch(() => {});
      if (own !== generation) throw new Error("Renderer stopped");
      canvas = document.createElement("canvas");
      canvas.width = width ?? video.videoWidth ?? 640;
      canvas.height = height ?? video.videoHeight ?? 360;
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
          if (!width && (canvas.width !== w || canvas.height !== h)) { canvas.width = w; canvas.height = h; }
          const { rgb, strength, dark } = getTint();
          ctx.filter = neutral ? "none" : `saturate(1.25) contrast(1.1)${dark ? " brightness(0.7)" : ""}`;
          const scale = Math.min(canvas.width / w, canvas.height / h);
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(video, (canvas.width - w * scale) / 2, (canvas.height - h * scale) / 2, w * scale, h * scale);
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
      output = canvas.captureStream(fps);
      return output;
    },
    stop() {
      generation++;
      running = false;
      if (raf) cancelAnimationFrame(raf);
      if (vfc && video?.cancelVideoFrameCallback) video.cancelVideoFrameCallback(vfc);
      if (video) video.srcObject = null;
      output?.getTracks().forEach((track) => track.stop());
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

export async function fetchDecartToken(fetcher = globalThis.fetch) {
  const response = await fetcher("/api/restyle/token", {
    headers: { "X-Genrator-Restyle": "1" }, cache: "no-store",
  });
  const data = await response.json();
  if (!response.ok || !data.apiKey) throw new Error(data.error || "Decart token unavailable");
  return data.apiKey;
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
  let session = null, prompt = "";
  const cleanup = (own) => {
    if (!own) return;
    own.cancelled = true;
    own.reject?.(new Error("Renderer stopped"));
    own.unwatch?.(); own.unwatch = null;
    try { own.client?.disconnect(); } catch { /* ignore */ }
    own.client = null;
    own.surface?.stop(); own.surface = null;
  };
  const active = (own) => session === own && !own.cancelled;
  return {
    name: "decart",
    async start(stream) {
      const own = { cancelled: false, latency: null };
      session = own;
      try {
        const { createDecartClient, models } = await (deps.loadDecartSdk?.() ?? import(DECART_SDK_URL));
        if (!active(own)) throw new Error("Renderer stopped");
        const model = models.realtime(config.DECART_MODEL ?? DECART_MODEL);
        const fps = typeof model.fps === "number" ? model.fps : model.fps?.ideal ?? model.fps?.max ?? 30;
        own.surface = (deps.makeDecartSurface ?? canvasSurface)({ width: model.width, height: model.height, fps, neutral: true });
        const input = await own.surface.start(stream, () => {}, () => ({ rgb: [0, 0, 0], strength: 0, dark: false }));
        if (!active(own)) throw new Error("Renderer stopped");
        const decart = createDecartClient({
          apiKeyProvider: () => fetchDecartToken(deps.fetch ?? globalThis.fetch), telemetry: false,
        });
        let resolveOut;
        const out = new Promise((resolve, reject) => { resolveOut = resolve; own.reject = reject; });
        // A connect failure may happen before we reach `await out`.
        out.catch(() => {});
        own.client = await decart.realtime.connect(input, {
          model,
          onRemoteStream: (remote) => {
            if (!active(own)) return;
            own.unwatch?.();
            own.unwatch = (deps.watchFrames ?? watchFrames)(remote, () => {
              if (active(own)) emitFrame(own.latency);
            });
            resolveOut(remote);
          },
          initialState: { prompt: { text: prompt || "a painterly fantasy world", enhance: false } },
        });
        if (!active(own)) throw new Error("Renderer stopped");
        own.client.on?.("stats", (stats) => {
          const ms = stats?.latency?.medianMs ?? stats?.medianMs ?? stats?.glassToGlass?.medianMs;
          if (Number.isFinite(ms)) own.latency = Math.round(ms);
        });
        own.client.on?.("error", (e) => console.warn("[restyler/decart]", e?.code));
        return await out;
      } catch (error) {
        cleanup(own);
        if (session === own) session = null;
        throw error;
      }
    },
    setPrompt(text) {
      prompt = text;
      if (session?.client) Promise.resolve(session.client.setPrompt(text, { enhance: false }))
        .catch(() => console.warn("[restyler/decart] prompt update failed"));
    },
    stop() {
      cleanup(session);
      session = null;
    },
  };
}

export const PROVIDERS = { fake: fakeProvider, decart: decartProvider };

// ---------------------------------------------------------------------------------------------

/**
 * @param {object} config  shared config (C10); RESTYLE_PROVIDER overrides PROVIDER
 * @param {object} [deps]  test seams: now, setInterval, clearInterval, makeSurface, loadDecartSdk, makeDecartSurface
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
  let generation = 0;
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
      const own = generation;
      // ok only once a real frame arrives; the fallback (T33) debounces the switch to raw.
      lastFrame = -Infinity;
      ok = false;
      timer = setI(check, CHECK_MS);
      try {
        if (prompt !== null) provider.setPrompt(prompt);
        const output = await provider.start(stream);
        if (own !== generation) throw new Error("Renderer stopped");
        return output;
      } catch (err) {
        if (own !== generation) throw err;
        if (timer) { clearI(timer); timer = null; }
        provider.stop();
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
      generation++;
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
