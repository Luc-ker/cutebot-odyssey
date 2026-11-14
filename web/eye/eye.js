// Robot's-eye display page (T31, whitepaper §7.2, §4): the main screen of the game.
// phone stream (T26) -> restyler (T28) -> full-screen video; `video.prompt` -> restyler.setPrompt.
// The raw phone feed always plays underneath, so a failing restyler still leaves a picture.
// Publishes `video.status {mode, latency_ms}` every second. Keys: F fullscreen, R force raw.
// Overlays (HUD T32, fallback T33, pulse T34, giant T35) load as optional modules.

import { connectHub } from "../common/hub.js";
import { receivePhoneStream, onStream } from "./receiver.js";
import { createRestyler } from "./restyler.js";

const $ = (id) => document.getElementById(id);
const stage = $("stage");
const rawVideo = $("raw");
const styledVideo = $("styled");

async function loadConfig() {
  try {
    return await (await import("../common/config.js")).loadConfig();
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

  const restyler = createRestyler(config);

  const [, fallback] = await Promise.all([
    optional("./pulse.js", "mountPulse", $("slot-pulse"), hub),
    optional("./fallback.js", "mountFallback", $("slot-fallback"), hub, restyler),
    optional("./giant.js", "mountGiant", $("slot-giant"), hub),
    optional("./hud.js", "mountHud", $("slot-hud"), hub),
  ]);

  // ---- mode: restyled or raw ----------------------------------------------------------------
  let forcedRaw = false;
  const mode = () => {
    if (forcedRaw) return "raw";
    // With the fallback module, it decides (debounced). Without it, follow the restyler directly.
    const raw = fallback ? fallback.isActive() : !restyler.status.ok;
    return raw ? "raw" : "restyled";
  };
  const applyMode = () => { stage.dataset.mode = mode(); };
  restyler.onStatus(applyMode);
  fallback?.onChange(applyMode);

  setInterval(() => {
    const m = mode();
    // Raw latency isn't measured; 0 means "no model in the loop".
    hub.pub("video.status", { mode: m, latency_ms: m === "restyled" ? restyler.status.latency_ms ?? 0 : 0 });
  }, 1000);

  // ---- prompt ------------------------------------------------------------------------------
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

  // ---- stream ------------------------------------------------------------------------------
  let current = null;
  async function useStream(stream) {
    if (!stream || stream === current) return;
    current = stream;
    rawVideo.srcObject = stream;
    rawVideo.play().catch(() => {});
    $("waiting").hidden = true;
    try {
      const out = await restyler.start(stream);
      if (current !== stream) return; // a newer stream arrived meanwhile
      styledVideo.srcObject = out;
      styledVideo.play().catch(() => {});
    } catch (e) {
      console.warn("[eye] restyler failed, showing the raw feed:", e.message);
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
    }
  });

  applyMode();
}

main().catch((e) => {
  console.error("[eye] failed to start", e);
  $("waiting").textContent = `Eye failed to start: ${e.message}`;
});
