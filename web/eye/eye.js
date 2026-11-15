// Robot's-eye display page (T31, whitepaper §7.2, §4): the main screen of the game.
// phone stream (T26) -> restyler (T28) -> full-screen video; `video.prompt` -> restyler.setPrompt.
// The raw phone feed always plays underneath, so a failing restyler still leaves a picture.
// Publishes `video.status {mode, latency_ms}` every second. Keys: F fullscreen, R force raw,
// Space start/stop the show, M listen to the song now for one new scene (controls.js, driven by `show.state`).
// Overlays (HUD T32, fallback T33, pulse T34) and the show controls load as optional modules. The giant
// effect (T35: dark shadow sweep and screen shake) is no longer mounted.
// A stopped show ends the AI video session (no renderer credits used) and dims the camera.
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
  // Status label names the locked world in stable mode ("AI Neon City live"), else a generic one.
  const liveName = (config.STABLE_KINGDOM_ENABLED && config.STABLE_WORLD_NAME) || "world";
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const hub = await connectHub(`${proto}//${location.host}/hub`, "eye");
  hub.onStatus?.((s) => { $("conn").hidden = s === "open"; });

  const restyler = createRestyler(config);

  const [, fallback] = await Promise.all([
    optional("./pulse.js", "mountPulse", $("slot-pulse"), hub),
    optional("./fallback.js", "mountFallback", $("slot-fallback"), hub, restyler),
    optional("./hud.js", "mountHud", $("slot-hud"), hub),
    optional("./frames.js", "startFrameSender", hub, rawVideo,
      { hz: config.VISION_HZ, width: config.FRAME_WIDTH }),
  ]);

  // ---- mode: restyled or raw ----------------------------------------------------------------
  let showRunning = true;
  // The renderer waits for the brain's show.state, so a page opened while the show is stopped never
  // opens an AI session. A brain that never answers (older build) counts as running after 4 s.
  let showKnown = false;
  setTimeout(() => { if (!showKnown) onShowState({ running: true, listening: false }); }, 4000);
  let forcedRaw = false;
  let rendererStarted = false;
  let rendererError = null;
  const mode = () => {
    if (forcedRaw || !showRunning) return "raw";
    // With the fallback module, it decides (debounced). Without it, follow the restyler directly.
    const raw = fallback ? fallback.isActive() : !restyler.status.ok;
    return raw ? "raw" : "restyled";
  };
  const applyMode = () => { stage.dataset.mode = mode(); };
  restyler.onStatus((status) => {
    applyMode();
    if (config.RESTYLE_PROVIDER !== "decart" || !rendererStarted || rendererError) return;
    $("renderer").textContent = status.ok
      ? `AI ${liveName} live` : "AI paused · showing camera";
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
      const w = env.data?.world;
      const p = w?.stable_prompt || w?.restyle_prompt; // built-in scenes carry their full prompt
      if (!gotPrompt && p) restyler.setPrompt(p);
    });
  }

  // ---- stream ------------------------------------------------------------------------------
  let current = null;
  async function useStream(stream) {
    if (!stream || stream === current) return;
    current = stream;
    rawVideo.srcObject = stream;
    rawVideo.play().catch(() => {});
    $("waiting").hidden = true;
    if (!showKnown) return; // onShowState starts it
    if (showRunning) await startRenderer(stream);
    else { $("renderer").textContent = "show stopped"; applyMode(); }
  }

  // Each start (or stop) bumps this, so a cancelled earlier start can't report over a newer one.
  let rendererRun = 0;
  async function startRenderer(stream) {
    const run = ++rendererRun;
    rendererStarted = false;
    rendererError = null;
    $("renderer").textContent = config.RESTYLE_PROVIDER === "decart"
      ? "connecting AI video…" : "Camera preview · AI renderer off";
    try {
      const out = await restyler.start(stream);
      if (run !== rendererRun || current !== stream || !showRunning) return; // superseded meanwhile
      styledVideo.srcObject = out;
      styledVideo.play().catch(() => {});
      rendererStarted = true;
      if (config.RESTYLE_PROVIDER === "decart") $("renderer").textContent = restyler.status.ok
        ? `AI ${liveName} live` : "AI connected · waiting for frames";
    } catch (e) {
      if (run !== rendererRun || current !== stream || !showRunning) return;
      console.warn("[eye] restyler failed, showing the raw feed:", e.message);
      rendererError = e.message;
      $("renderer").textContent = `AI rendering unavailable: ${e.message}`;
    }
    applyMode();
  }
  onStream(useStream);
  receivePhoneStream(hub).then(useStream);

  // ---- show controls -----------------------------------------------------------------------
  function onShowState(s) {
    stage.dataset.show = s.running ? "running" : "stopped";
    stage.dataset.listening = s.running && s.listening ? "on" : "off";
    const first = !showKnown;
    showKnown = true;
    if (s.running === showRunning && !first) return;
    showRunning = s.running;
    if (first && showRunning) {
      if (current) startRenderer(current);
      return;
    }
    if (!showRunning) {
      rendererRun++;
      restyler.stop(); // ends the renderer session, so no credits are spent while stopped
      rendererStarted = false;
      rendererError = null;
      styledVideo.srcObject = null;
      $("renderer").textContent = "show stopped";
      applyMode();
    } else if (current) {
      startRenderer(current);
    }
  }
  await optional("./controls.js", "mountControls", stage, hub, { onState: onShowState });

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
    }
  });

  applyMode();
}

main().catch((e) => {
  console.error("[eye] failed to start", e);
  $("waiting").textContent = `Eye failed to start: ${e.message}`;
});
