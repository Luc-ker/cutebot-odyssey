// Robot's-eye display page (T31, whitepaper §7.2, §4): the main screen of the game.
// phone stream (T26) -> restyler (T28) -> full-screen video; `video.prompt` -> restyler.setPrompt.
// The raw phone feed always plays underneath, so a failing restyler still leaves a picture.
// Publishes `video.status {mode, latency_ms}` every second. Keys: F fullscreen, R force raw,
// D debug outlines (local renderer).
// Overlays (HUD T32, fallback T33, pulse T34, giant T35) load as optional modules.
// The raw feed is also sampled at VISION_HZ and sent to the vision service on `camera.frame` (frames.js):
// the phone's view is the only camera, so this page must be open for objects and giants to be seen.

import { connectHub } from "../common/hub.js";
import { receivePhoneStream, onStream } from "./receiver.js";
import { createRestyler, stablePrompt } from "./restyler.js";

const $ = (id) => document.getElementById(id);
const stage = $("stage");
const rawVideo = $("raw");
const styledVideo = $("styled");

async function loadConfig() {
  try {
    const config = await (await import("../common/config.js")).loadConfig();
    const response = await fetch("/api/restyle/config", { cache: "no-store" });
    if (response.ok) Object.assign(config, await response.json());
    return config;
  } catch (e) {
    console.warn("[eye] config not loaded, using defaults:", e.message);
    return {};
  }
}

/** Import an optional overlay and call its mount function; failures only warn. */
async function optional(path, mountName, ...args) {
  try {
    const mod = await import(path);
    return await mod[mountName](...args);
  } catch (e) {
    console.warn(`[eye] optional module ${path} not loaded:`, e.message);
    return null;
  }
}

async function main() {
  const config = await loadConfig();
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const hub = await connectHub(`${proto}//${location.host}/hub`, "eye");
  hub.onStatus?.((s) => { $("conn").hidden = s === "open"; });

  // The local renderer reads vision.state / world.objects itself, so it gets the hub.
  const restyler = createRestyler(config, { hub });
  const providerName = restyler.provider.name;
  const labels = {
    local: { connecting: "Starting local renderer…", live: "Local renderer", paused: "Renderer paused · showing camera" },
    decart: { connecting: "Connecting Kingdom renderer…", live: "AI Kingdom live", paused: "AI paused · showing camera" },
  }[providerName];

  const [, fallback] = await Promise.all([
    optional("./pulse.js", "mountPulse", $("slot-pulse"), hub),
    optional("./fallback.js", "mountFallback", $("slot-fallback"), hub, restyler),
    optional("./giant.js", "mountGiant", $("slot-giant"), hub),
    optional("./hud.js", "mountHud", $("slot-hud"), hub),
    optional("./frames.js", "startFrameSender", hub, rawVideo,
      { hz: config.VISION_HZ, width: config.FRAME_WIDTH }),
  ]);

  // ---- mode: restyled or raw ----------------------------------------------------------------
  let forcedRaw = false;
  let rendererStarted = false;
  let rendererError = null;
  const mode = () => {
    if (forcedRaw) return "raw";
    // With the fallback module, it decides (debounced). Without it, follow the restyler directly.
    const raw = fallback ? fallback.isActive() : !restyler.status.ok;
    return raw ? "raw" : "restyled";
  };
  const applyMode = () => { stage.dataset.mode = mode(); };
  restyler.onStatus((status) => {
    applyMode();
    if (!labels || !rendererStarted || rendererError) return;
    $("renderer").textContent = status.ok ? labels.live : labels.paused;
  });
  fallback?.onChange(applyMode);

  setInterval(() => {
    const m = mode();
    // Raw latency isn't measured; 0 means "no model in the loop".
    hub.pub("video.status", { mode: m, latency_ms: m === "restyled" ? restyler.status.latency_ms ?? 0 : 0 });
  }, 1000);

  // ---- prompt ------------------------------------------------------------------------------
  const lockedPrompt = stablePrompt(config);
  if (lockedPrompt) {
    // Stable Kingdom mode: one prompt for the whole run, set before the renderer connects, so
    // objects, hands and world events can never restyle the scene mid-demo.
    restyler.setPrompt(lockedPrompt);
  } else {
    let gotPrompt = false;
    hub.sub("video.prompt", (env) => {
      if (typeof env.data?.prompt !== "string") return;
      gotPrompt = true;
      restyler.setPrompt(env.data.prompt);
    });
    // Until the composer (T29) speaks, use the world's own prompt so the style is right from the start.
    hub.sub("world.current", (env) => {
      const p = env.data?.world?.restyle_prompt;
      if (!gotPrompt && p) restyler.setPrompt(p);
    });
  }

  // ---- stream ------------------------------------------------------------------------------
  let current = null;
  async function useStream(stream) {
    if (!stream || stream === current) return;
    current = stream;
    rendererStarted = false;
    rendererError = null;
    rawVideo.srcObject = stream;
    rawVideo.play().catch(() => {});
    $("waiting").hidden = true;
    $("renderer").textContent = labels ? labels.connecting : "Camera preview · renderer off";
    try {
      const out = await restyler.start(stream);
      if (current !== stream) return; // a newer stream arrived meanwhile
      styledVideo.srcObject = out;
      styledVideo.play().catch(() => {});
      rendererStarted = true;
      if (labels) $("renderer").textContent = restyler.status.ok ? labels.live : "Renderer ready · waiting for frames";
    } catch (e) {
      if (current !== stream) return;
      console.warn("[eye] restyler failed, showing the raw feed:", e.message);
      rendererError = e.message;
      $("renderer").textContent = `Rendering unavailable: ${e.message}`;
    }
    applyMode();
  }
  onStream(useStream);
  receivePhoneStream(hub).then(useStream);

  // ---- keys --------------------------------------------------------------------------------
  document.addEventListener("keydown", (e) => {
    if (e.repeat || e.ctrlKey || e.metaKey || e.altKey) return;
    const key = e.key.toLowerCase();
    if (key === "f") {
      if (document.fullscreenElement) document.exitFullscreen();
      else document.documentElement.requestFullscreen().catch(() => {});
    } else if (key === "r") {
      forcedRaw = !forcedRaw;
      fallback?.setForced(forcedRaw);
      applyMode();
      console.info(`[eye] raw mode ${forcedRaw ? "forced" : "auto"}`);
    } else if (key === "d") {
      const c = restyler.provider.compositor;
      if (c) c.setDebug(!c.debug);
    }
  });

  applyMode();
}

main().catch((e) => {
  console.error("[eye] failed to start", e);
  $("waiting").textContent = `Eye failed to start: ${e.message}`;
});
