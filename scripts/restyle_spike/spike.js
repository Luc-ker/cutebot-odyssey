// Restyle spike page (T27). Throwaway: measures a provider through the same adapter the eye page uses.
// Measures: output fps, provider-reported latency, prompt-change time (prompt sent -> output colour
// shifts), and glass-to-glass lag (brightness step in raw -> same step in output).
import { createRestyler } from "../../web/eye/restyler.js";

const $ = (id) => document.getElementById(id);
const raw = $("raw");
const out = $("out");
const results = { provider: null, started_at: null, fps: [], provider_latency_ms: [], prompt_change_ms: [], lag_ms: [] };
const PRESETS = [
  "a stormy ocean at dusk, rain, wooden ships, lantern light, painterly",
  "a volcanic wasteland, rivers of lava, ash sky, glowing embers",
  "a snowy forest at night, moonlight, pine trees, soft blue light",
  "a sunny medieval kingdom, rolling green hills, stone castles",
];
let presetIdx = 0;
let restyler = null;
let camera = null;

const log = (msg) => { $("log").textContent = `${new Date().toISOString().slice(11, 23)} ${msg}\n` + $("log").textContent; };
const median = (a) => (a.length ? [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)] : null);

// Mean luminance and colour of a video, sampled small.
function sampler(video) {
  const c = document.createElement("canvas");
  c.width = 32; c.height = 18;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  return () => {
    if (!video.videoWidth) return null;
    ctx.drawImage(video, 0, 0, 32, 18);
    const d = ctx.getImageData(0, 0, 32, 18).data;
    let r = 0, g = 0, b = 0;
    for (let i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; }
    const n = d.length / 4;
    return { r: r / n, g: g / n, b: b / n, y: (0.299 * r + 0.587 * g + 0.114 * b) / n };
  };
}
const sampleRaw = sampler(raw);
const sampleOut = sampler(out);

// ---- prompt-change timing ---------------------------------------------------------------------
let promptProbe = null; // {t0, base}
function sendPrompt(text) {
  if (!restyler) return;
  const s = sampleOut();
  promptProbe = s ? { t0: performance.now(), base: s } : null;
  restyler.setPrompt(text);
  log(`prompt -> ${text.slice(0, 60)}…`);
}

// ---- lag test -------------------------------------------------------------------------------
let lag = null; // {prevRaw, prevOut, pendingRaw: [t]}
const STEP = 35; // luminance jump that counts as an edge

function loop() {
  const t = performance.now();
  const r = sampleRaw();
  const o = sampleOut();
  if (promptProbe && o) {
    const d = Math.hypot(o.r - promptProbe.base.r, o.g - promptProbe.base.g, o.b - promptProbe.base.b);
    if (d > 25) {
      const ms = Math.round(t - promptProbe.t0);
      results.prompt_change_ms.push(ms);
      log(`prompt took effect after ~${ms} ms`);
      promptProbe = null;
    } else if (t - promptProbe.t0 > 15000) {
      log("prompt change not detected within 15 s");
      promptProbe = null;
    }
  }
  if (lag && r && o) {
    if (lag.prevRaw != null && Math.abs(r.y - lag.prevRaw) > STEP) lag.pendingRaw.push(t);
    if (lag.prevOut != null && Math.abs(o.y - lag.prevOut) > STEP && lag.pendingRaw.length) {
      const ms = Math.round(t - lag.pendingRaw.shift());
      if (ms < 5000) { results.lag_ms.push(ms); log(`glass-to-glass lag ~${ms} ms`); }
    }
    lag.prevRaw = r.y;
    lag.prevOut = o.y;
  }
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

// ---- controls -------------------------------------------------------------------------------
$("start").onclick = async () => {
  try {
    camera ??= await navigator.mediaDevices.getUserMedia({ video: { width: 960, height: 540, frameRate: 30 }, audio: false });
    raw.srcObject = camera;
    restyler?.stop();
    const provider = $("provider").value;
    restyler = createRestyler({ RESTYLE_PROVIDER: provider });
    Object.assign(results, { provider, started_at: new Date().toISOString(), fps: [], provider_latency_ms: [], prompt_change_ms: [], lag_ms: [] });
    restyler.onStatus((s) => {
      if (s.ok) results.fps.push(s.fps);
      if (Number.isFinite(s.latency_ms) && s.latency_ms > 0) results.provider_latency_ms.push(s.latency_ms);
      $("stats").textContent =
        `provider ${provider}  ok ${s.ok}  fps ${s.fps}  provider latency ${s.latency_ms ?? "n/a"} ms\n` +
        `median fps ${median(results.fps) ?? "-"}  median lag ${median(results.lag_ms) ?? "-"} ms  ` +
        `median prompt change ${median(results.prompt_change_ms) ?? "-"} ms`;
    });
    restyler.setPrompt($("prompt").value);
    const t0 = performance.now();
    out.srcObject = await restyler.start(camera);
    log(`started ${provider}; output stream after ${Math.round(performance.now() - t0)} ms`);
  } catch (e) {
    log(`start failed: ${e.message}`);
  }
};
$("stop").onclick = () => { restyler?.stop(); restyler = null; log("stopped"); };
$("send").onclick = () => sendPrompt($("prompt").value);
$("prompt").onkeydown = (e) => { if (e.key === "Enter") sendPrompt($("prompt").value); };
$("preset").onclick = () => {
  presetIdx = (presetIdx + 1) % PRESETS.length;
  $("prompt").value = PRESETS[presetIdx];
  sendPrompt(PRESETS[presetIdx]);
};
$("lag").onclick = () => { lag = { prevRaw: null, prevOut: null, pendingRaw: [] }; log("lag test armed: cover and uncover the camera"); };
$("copy").onclick = async () => {
  const summary = {
    ...results,
    median_fps: median(results.fps),
    median_lag_ms: median(results.lag_ms),
    median_prompt_change_ms: median(results.prompt_change_ms),
    median_provider_latency_ms: median(results.provider_latency_ms),
    user_agent: navigator.userAgent,
  };
  const text = JSON.stringify(summary, null, 2);
  try { await navigator.clipboard.writeText(text); log("results copied"); } catch { log(text); }
};
