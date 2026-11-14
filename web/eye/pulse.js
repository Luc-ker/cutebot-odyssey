// Beat pulse on the robot's-eye view (T34, whitepaper §7.9).
// Each audio.beat kicks a short brightness / glow / vignette pulse. Its size follows the music's energy
// (audio.features), it settles to nothing when the music is silent, and prefers-reduced-motion shrinks
// it to a quarter. Driven by CSS variables:
//   --pulse   0..1, set on the container and on <html> (the eye page uses it for video brightness)
// Runs locally from the hub's audio topics: no network round trip beyond the LAN hub.

const DECAY_MS = 180; // time constant of the fade after each beat
const SILENT_DECAY_MS = 60;
const REDUCED_SCALE = 0.25;

/** Pure: how big a pulse a beat makes. Exported for tests and tuning. */
export function pulseSize({ strength = 1, energy = 0.5, silent = false, reduced = false } = {}) {
  if (silent) return 0;
  const e = Math.max(0, Math.min(1, energy));
  const s = Math.max(0, Math.min(1, strength));
  const size = (0.25 + 0.75 * e) * (0.5 + 0.5 * s);
  return reduced ? size * REDUCED_SCALE : size;
}

function ensureCss(doc, href) {
  if (!doc.head?.querySelector || doc.head.querySelector(`link[href="${href}"]`)) return;
  const link = doc.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  doc.head.append(link);
}

export function mountPulse(container, hub) {
  const doc = container.ownerDocument ?? document;
  ensureCss(doc, new URL("./pulse.css", import.meta.url).href);

  const root = doc.createElement("div");
  root.className = "pulse";
  root.innerHTML = '<div class="pulse-glow"></div><div class="pulse-vignette"></div>';
  container.append(root);

  const mq = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)");
  let reduced = Boolean(mq?.matches);
  mq?.addEventListener?.("change", (e) => { reduced = e.matches; });

  let energy = 0.5;
  let silent = false;
  let level = 0;
  let last = performance.now();
  let raf = null;

  const write = (v) => {
    const s = v.toFixed(3);
    root.style.setProperty("--pulse", s);
    doc.documentElement.style.setProperty("--pulse", s);
  };

  const frame = (t) => {
    const dt = t - last;
    last = t;
    level *= Math.exp(-dt / (silent ? SILENT_DECAY_MS : DECAY_MS));
    if (level < 0.002) { level = 0; write(0); raf = null; return; }
    write(level);
    raf = requestAnimationFrame(frame);
  };
  const kick = () => {
    if (raf == null) { last = performance.now(); raf = requestAnimationFrame(frame); }
  };

  const offs = [
    hub.sub("audio.features", (env) => {
      const d = env.data ?? {};
      if (Number.isFinite(d.energy)) energy = d.energy;
      silent = Boolean(d.silent);
      if (silent) kick(); // fade any pulse out quickly
    }),
    hub.sub("audio.beat", (env) => {
      const size = pulseSize({ strength: env.data?.strength ?? 1, energy, silent, reduced });
      if (size <= 0) return;
      level = Math.max(level, size);
      write(level);
      kick();
    }),
    hub.sub("system.reset", () => { level = 0; write(0); }),
  ];

  return {
    root,
    destroy() {
      if (raf != null) cancelAnimationFrame(raf);
      offs.forEach((off) => typeof off === "function" && off());
      write(0);
      root.remove();
    },
  };
}
