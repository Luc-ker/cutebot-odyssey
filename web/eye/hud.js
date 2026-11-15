// Robot's-eye HUD overlay (T32, whitepaper §7.2).
// Left edge: the world name set vertically under a seal in its palette colour. Bottom-centre:
// "ahead — The Salt Queen  ship" while
// the robot faces a known object, fading out 2 s after the target goes. Corner dot pops on each beat.
// Top right, beside the beat dot, a music line: "Song picked up" while music plays, "rendering new scene" while
// Gemini composes a world from it, then the outcome for a few seconds.
// Topics (C3): world.current, world.objects, robot.state, audio.beat, audio.features, world.composing,
// system.reset.

const HIDE_AFTER_MS = 2000;
const POP_MS = 160;
export const HEAR_AFTER_MS = 600;      // continuous music before "Song picked up" shows
export const QUIET_AFTER_MS = 1500;    // continuous silence before it goes away
const FEATURES_STALE_MS = 2000;        // no audio.features at all (mic or brain down): stop showing it
const COMPOSING_MAX_MS = 45000;        // a lost result never leaves "rendering" up forever
const OUTCOME_MS = { done: 4000, kept: 2500, failed: 2500, quiet: 2500 };

/** Pure: the music line's text and look for a state, or null to hide it. Exported for tests. */
export function musicLine({ hearing = false, composing = false, outcome = null } = {}) {
  if (composing) return { text: "rendering new scene", cls: "composing" };
  if (outcome?.state === "done") return { text: outcome.name || "new scene", cls: "done" };
  if (outcome?.state === "kept") return { text: "same mood · scene kept", cls: "kept" };
  if (outcome?.state === "failed") return { text: "couldn't render · scene kept", cls: "failed" };
  if (outcome?.state === "quiet") return { text: "no song heard", cls: "failed" };
  if (hearing) return { text: "song picked up", cls: "hearing" };
  return null;
}

const LOCAL_COLOURS = {
  teal: [0, 128, 128], grey: [128, 128, 128], gray: [128, 128, 128], gold: [230, 180, 50],
  red: [200, 40, 40], orange: [240, 130, 30], yellow: [240, 210, 60], green: [50, 160, 70],
  blue: [40, 100, 210], purple: [130, 60, 180], pink: [235, 120, 170], white: [240, 240, 240],
  black: [20, 20, 20], silver: [190, 190, 200], brown: [130, 80, 40], crimson: [180, 20, 50],
  amber: [255, 180, 0], ivory: [250, 245, 225], violet: [140, 80, 220], cyan: [40, 200, 220],
};

/** Colour word -> rgb without the shared table: last known word wins, else a stable hash hue. */
export function localColour(word = "") {
  const parts = String(word).toLowerCase().split(/\s+/).reverse();
  for (const p of parts) if (LOCAL_COLOURS[p]) return LOCAL_COLOURS[p];
  let h = 0;
  for (const ch of String(word)) h = (h * 31 + ch.charCodeAt(0)) % 360;
  const f = (n) => { const k = (n + h / 30) % 12; return Math.round(255 * (0.6 - 0.35 * Math.max(-1, Math.min(k - 3, 9 - k, 1)))); };
  return [f(0), f(8), f(4)];
}

async function defaultColourFor() {
  try {
    const m = await import("../common/colours.js");
    return m.colourFor;
  } catch {
    return async (w) => localColour(w);
  }
}

export const prettyRole = (role) => String(role ?? "").replace(/_/g, " ");

function ensureCss(doc, href) {
  if (!doc.head?.querySelector || doc.head.querySelector(`link[href="${href}"]`)) return;
  const link = doc.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  doc.head.append(link);
}

/**
 * @param {HTMLElement} container  slot to render into
 * @param {{sub: Function}} hub
 * @param {object} [opts]  test seams: colourFor, setTimeout, clearTimeout
 */
export function mountHud(container, hub, opts = {}) {
  const doc = container.ownerDocument ?? globalThis.document;
  const setT = opts.setTimeout ?? globalThis.setTimeout.bind(globalThis);
  const clearT = opts.clearTimeout ?? globalThis.clearTimeout.bind(globalThis);
  const colourFor = opts.colourFor ? Promise.resolve(opts.colourFor) : defaultColourFor();
  try { ensureCss(doc, new URL("./hud.css", import.meta.url).href); } catch { /* non-browser */ }

  const el = (cls) => { const e = doc.createElement("div"); e.className = cls; return e; };
  const root = el("hud");
  const world = el("hud-world");
  const ahead = el("hud-ahead");
  const aheadLabel = el("hud-ahead-label");
  const aheadName = el("hud-ahead-name");
  const aheadRole = el("hud-ahead-role");
  aheadLabel.textContent = "ahead";
  ahead.append(aheadLabel, aheadName, aheadRole);
  const beat = el("hud-beat");
  const music = el("hud-music");
  root.append(world, ahead, beat, music);
  container.append(root);

  let objects = new Map();
  let facingId = null;
  let hideTimer = null;
  let popTimer = null;
  let worldId = null;
  const now = opts.now ?? (() => Date.now());
  const ms = { hearing: false, composing: false, outcome: null };
  let loudSince = null;
  let lastLoud = -Infinity;
  let staleTimer = null;
  let composingTimer = null;
  let outcomeTimer = null;

  function drawMusic() {
    const line = musicLine(ms);
    for (const c of ["hearing", "composing", "done", "kept", "failed"]) music.classList.remove(c);
    if (!line) { music.classList.remove("visible"); return; }
    music.textContent = line.text;
    music.classList.add("visible");
    music.classList.add(line.cls);
  }

  function onFeatures(d = {}) {
    const t = now();
    if (staleTimer) clearT(staleTimer);
    staleTimer = setT(() => { staleTimer = null; loudSince = null; ms.hearing = false; drawMusic(); }, FEATURES_STALE_MS);
    if (!d.silent) {
      lastLoud = t;
      if (loudSince == null) loudSince = t;
      if (!ms.hearing && t - loudSince >= HEAR_AFTER_MS) { ms.hearing = true; drawMusic(); }
    } else {
      loudSince = null;
      if (ms.hearing && t - lastLoud >= QUIET_AFTER_MS) { ms.hearing = false; drawMusic(); }
    }
  }

  function onComposing(d = {}) {
    if (composingTimer) { clearT(composingTimer); composingTimer = null; }
    if (outcomeTimer) { clearT(outcomeTimer); outcomeTimer = null; }
    if (d.state === "composing") {
      ms.composing = true;
      ms.outcome = null;
      composingTimer = setT(() => { composingTimer = null; ms.composing = false; drawMusic(); }, COMPOSING_MAX_MS);
    } else if (OUTCOME_MS[d.state]) {
      ms.composing = false;
      ms.outcome = { state: d.state, name: d.name };
      outcomeTimer = setT(() => { outcomeTimer = null; ms.outcome = null; drawMusic(); }, OUTCOME_MS[d.state]);
    }
    drawMusic();
  }

  function showAhead() {
    const obj = facingId == null ? null : objects.get(facingId);
    if (obj && (obj.name || obj.role)) {
      if (hideTimer) { clearT(hideTimer); hideTimer = null; }
      aheadName.textContent = obj.name || prettyRole(obj.role);
      aheadRole.textContent = obj.name && obj.role ? prettyRole(obj.role) : "";
      ahead.classList.add("visible");
    } else if (ahead.classList.contains("visible") && !hideTimer) {
      hideTimer = setT(() => { hideTimer = null; ahead.classList.remove("visible"); }, HIDE_AFTER_MS);
    }
  }

  async function setWorld(w) {
    const info = w?.world ?? {};
    world.textContent = info.name ?? "";
    world.classList.toggle("visible", Boolean(info.name));
    if (w?.id === worldId) return;
    worldId = w?.id ?? null;
    const palette = info.palette ?? [];
    if (!palette.length) return;
    const lookup = await colourFor;
    const rgbs = await Promise.all(palette.map((p) => Promise.resolve(lookup(p)).catch(() => localColour(p))));
    const [a, b, c] = [rgbs[0], rgbs[1] ?? rgbs[0], rgbs[2] ?? rgbs[0]];
    world.style.setProperty("--hud-accent", `rgb(${c.join(",")})`);
    world.style.setProperty("--hud-from", `rgb(${a.join(",")})`);
    world.style.setProperty("--hud-to", `rgb(${b.join(",")})`);
    beat.style.setProperty("--hud-accent", `rgb(${c.join(",")})`);
    music.style.setProperty("--hud-accent", `rgb(${c.join(",")})`);
  }

  const offs = [
    hub.sub("world.current", (env) => setWorld(env.data?.world)),
    hub.sub("world.objects", (env) => {
      objects = new Map((env.data?.objects ?? []).map((o) => [o.id, o]));
      showAhead();
    }),
    hub.sub("robot.state", (env) => {
      facingId = env.data?.facing_id ?? null;
      showAhead();
    }),
    hub.sub("audio.beat", (env) => {
      const s = Math.max(0.3, Math.min(1, env.data?.strength ?? 1));
      beat.style.setProperty("--beat-strength", String(s));
      beat.classList.remove("pop");
      void beat.offsetWidth; // restart the CSS animation
      beat.classList.add("pop");
      if (popTimer) clearT(popTimer);
      popTimer = setT(() => beat.classList.remove("pop"), POP_MS);
    }),
    hub.sub("audio.features", (env) => onFeatures(env.data ?? {})),
    hub.sub("world.composing", (env) => onComposing(env.data ?? {})),
    hub.sub("system.reset", () => {
      for (const t of [staleTimer, composingTimer, outcomeTimer]) if (t) clearT(t);
      staleTimer = composingTimer = outcomeTimer = null;
      loudSince = null;
      Object.assign(ms, { hearing: false, composing: false, outcome: null });
      drawMusic();
      objects = new Map();
      facingId = null;
      worldId = null;
      world.textContent = "";
      world.classList.remove("visible");
      ahead.classList.remove("visible");
    }),
  ];

  return {
    root,
    destroy() {
      offs.forEach((off) => typeof off === "function" && off());
      if (hideTimer) clearT(hideTimer);
      if (popTimer) clearT(popTimer);
      for (const t of [staleTimer, composingTimer, outcomeTimer]) if (t) clearT(t);
      root.remove?.();
    },
  };
}
