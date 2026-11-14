// Robot's-eye HUD overlay (T32, whitepaper §7.2).
// Top-left: world name tinted by the palette. Bottom-centre: "Ahead: The Salt Queen (ship)" while
// the robot faces a known object, fading out 2 s after the target goes. Corner dot pops on each beat.
// Topics (C3): world.current, world.objects, robot.state, audio.beat, system.reset.

const HIDE_AFTER_MS = 2000;
const POP_MS = 160;

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
  const beat = el("hud-beat");
  root.append(world, ahead, beat);
  container.append(root);

  let objects = new Map();
  let facingId = null;
  let hideTimer = null;
  let popTimer = null;
  let worldId = null;

  function showAhead() {
    const obj = facingId == null ? null : objects.get(facingId);
    if (obj && (obj.name || obj.role)) {
      if (hideTimer) { clearT(hideTimer); hideTimer = null; }
      ahead.textContent = obj.name
        ? `Ahead: ${obj.name}${obj.role ? ` (${prettyRole(obj.role)})` : ""}`
        : `Ahead: ${prettyRole(obj.role)}`;
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
    hub.sub("system.reset", () => {
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
      root.remove?.();
    },
  };
}
