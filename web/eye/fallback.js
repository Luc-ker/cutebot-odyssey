// Raw-feed fallback mode (T33, whitepaper §7.15).
// When the restyler reports ok:false for more than 1.5 s, the eye shows the plain camera feed under a
// palette-coloured gradient and vignette, with the facing object's role label drawn large, so the game
// carries on. Back to restyled once ok has held for 3 s.
//
// mountFallback(container, hub, restyler) -> {isActive(), onChange(cb), setForced(bool), destroy()}
// The eye page (T31) hides the restyled video while isActive() is true.

const BAD_FOR_MS = 1500;
const GOOD_FOR_MS = 3000;
const CHECK_MS = 250;

const LOCAL_COLOURS = {
  teal: [0, 128, 128], grey: [128, 128, 128], gray: [128, 128, 128], gold: [230, 180, 50],
  red: [200, 40, 40], orange: [240, 130, 30], green: [50, 160, 70], blue: [40, 100, 210],
  purple: [130, 60, 180], white: [235, 235, 245], black: [20, 20, 20], amber: [255, 180, 0],
};
const localColour = (word = "") => {
  for (const p of String(word).toLowerCase().split(/\s+/).reverse()) if (LOCAL_COLOURS[p]) return LOCAL_COLOURS[p];
  return [90, 90, 110];
};

async function defaultColourFor() {
  try { return (await import("../common/colours.js")).colourFor; } catch { return async (w) => localColour(w); }
}

/**
 * Pure state machine: feed it restyler statuses and the time, ask whether fallback is active.
 * Exported for tests.
 */
export function createFallbackState() {
  let badSince = null;
  let goodSince = null;
  let active = false;
  return {
    status(ok, now) {
      if (ok) { badSince = null; goodSince ??= now; }
      else { goodSince = null; badSince ??= now; }
    },
    /** Returns true when the active flag changed. */
    evaluate(now) {
      const was = active;
      if (!active && badSince != null && now - badSince > BAD_FOR_MS) active = true;
      else if (active && goodSince != null && now - goodSince >= GOOD_FOR_MS) active = false;
      return was !== active;
    },
    get active() { return active; },
    reset() { badSince = goodSince = null; active = false; },
  };
}

function ensureCss(doc, href) {
  if (!doc.head?.querySelector || doc.head.querySelector(`link[href="${href}"]`)) return;
  const link = doc.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  doc.head.append(link);
}

/**
 * @param {HTMLElement} container
 * @param {{sub: Function, pub: Function}} hub
 * @param {{onStatus: Function, status?: object}} restyler
 * @param {object} [opts] test seams: now, setInterval, clearInterval, colourFor
 */
export function mountFallback(container, hub, restyler, opts = {}) {
  const doc = container.ownerDocument ?? globalThis.document;
  const now = opts.now ?? (() => performance.now());
  const setI = opts.setInterval ?? globalThis.setInterval.bind(globalThis);
  const clearI = opts.clearInterval ?? globalThis.clearInterval.bind(globalThis);
  const colourFor = opts.colourFor ? Promise.resolve(opts.colourFor) : defaultColourFor();
  try { ensureCss(doc, new URL("./fallback.css", import.meta.url).href); } catch { /* non-browser */ }

  const el = (cls) => { const e = doc.createElement("div"); e.className = cls; return e; };
  const root = el("fallback");
  const tint = el("fb-tint");
  const vignette = el("fb-vignette");
  const badge = el("fb-badge");
  const label = el("fb-label");
  badge.textContent = "Camera view · AI restyle offline";
  root.append(tint, vignette, badge, label);
  container.append(root);

  const state = createFallbackState();
  const listeners = new Set();
  let forced = false;
  let latency = 0;
  let shown = false;
  let objects = new Map();
  let facingId = null;

  const isActive = () => forced || state.active;

  function apply() {
    const on = isActive();
    if (on === shown) return;
    shown = on;
    root.classList.toggle("active", on);
    hub.pub("video.status", { mode: on ? "raw" : "restyled", latency_ms: on ? 0 : latency });
    listeners.forEach((cb) => { try { cb(on); } catch (e) { console.error(e); } });
  }

  function drawLabel() {
    const o = facingId == null ? null : objects.get(facingId);
    label.textContent = o ? `${o.name ?? ""}${o.role ? ` · ${String(o.role).replace(/_/g, " ")}` : ""}` : "";
    label.classList.toggle("visible", Boolean(o));
    if (o?.behaviour) label.dataset.behaviour = o.behaviour;
  }

  async function setPalette(world) {
    const palette = world?.world?.palette ?? [];
    if (!palette.length) return;
    const lookup = await colourFor;
    const rgbs = await Promise.all(palette.map((p) => Promise.resolve(lookup(p)).catch(() => localColour(p))));
    ["--fb-c1", "--fb-c2", "--fb-c3"].forEach((v, i) => {
      const c = rgbs[i] ?? rgbs[0];
      root.style.setProperty(v, `rgb(${c.join(",")})`);
    });
  }

  const offStatus = restyler.onStatus((s) => {
    if (Number.isFinite(s?.latency_ms)) latency = s.latency_ms;
    state.status(Boolean(s?.ok), now());
    if (state.evaluate(now())) apply();
  });
  const timer = setI(() => { if (state.evaluate(now())) apply(); }, CHECK_MS);

  const offs = [
    hub.sub("world.current", (env) => setPalette(env.data?.world)),
    hub.sub("world.objects", (env) => {
      objects = new Map((env.data?.objects ?? []).map((o) => [o.id, o]));
      drawLabel();
    }),
    hub.sub("robot.state", (env) => { facingId = env.data?.facing_id ?? null; drawLabel(); }),
    hub.sub("system.reset", () => { objects = new Map(); facingId = null; drawLabel(); }),
  ];

  return {
    root,
    isActive,
    onChange(cb) { listeners.add(cb); return () => listeners.delete(cb); },
    setForced(on) { forced = Boolean(on); apply(); },
    destroy() {
      clearI(timer);
      if (typeof offStatus === "function") offStatus();
      offs.forEach((off) => typeof off === "function" && off());
      root.remove?.();
    },
  };
}
