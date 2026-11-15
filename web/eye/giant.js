// Giant arrival effect on the robot's-eye view (T35, whitepaper §7.10).
// world.event giant_enter: the top of the screen darkens, a shadow sweeps down and the view shakes.
// No on-screen caption: the effect is wordless.
// giant_leave (last giant gone): the shadow lifts. At most one effect every 4 s; more enters in that
// window keep the shadow but don't replay the effect.

const RATE_MS = 4000;
const SHAKE_MS = 600;
const LOST_MS = 2000;

function ensureCss(doc, href) {
  if (!doc.head?.querySelector || doc.head.querySelector(`link[href="${href}"]`)) return;
  const link = doc.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  doc.head.append(link);
}

export function mountGiant(container, hub, opts = {}) {
  const doc = container.ownerDocument ?? document;
  const now = opts.now ?? (() => performance.now());
  ensureCss(doc, new URL("./giant.css", import.meta.url).href);

  const root = doc.createElement("div");
  root.className = "giant";
  root.innerHTML = '<div class="giant-shadow"></div>';
  container.append(root);
  const shadow = root.querySelector(".giant-shadow");
  const stage = container.closest?.(".stage") ?? container.parentElement ?? doc.body;
  const reduced = () => Boolean(globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches);

  const giants = new Set();
  const lastSeen = new Map(); // giant id -> time last confirmed by an event or vision.state
  const kinds = new Map(); // giant id -> "hand" | "person", from vision.state
  let lastEffect = -Infinity;
  let shakeTimer = null;

  function play(kind) {
    lastEffect = now();
    // Restart the sweep animation even if the class is already there.
    shadow.classList.remove("sweep");
    void shadow.offsetWidth;
    shadow.classList.add("sweep");

    if (!reduced()) {
      stage.classList.add("giant-shake");
      clearTimeout(shakeTimer);
      shakeTimer = setTimeout(() => stage.classList.remove("giant-shake"), SHAKE_MS);
    }
  }

  function sync() { root.classList.toggle("active", giants.size > 0); }

  function clearAll() {
    giants.clear();
    lastSeen.clear();
    kinds.clear();
    sync();
    stage.classList.remove("giant-shake");
  }

  const offs = [
    hub.sub("world.event", (env) => {
      const d = env.data ?? {};
      // C3 lists giant_enter as {id, kind, edge}, but `kind` is already "giant_enter" on a
      // world.event, so hand vs person comes from vision.state (by giant id) instead.
      if (d.kind === "giant_enter") {
        const id = String(d.id);
        giants.add(id);
        lastSeen.set(id, now());
        sync();
        if (now() - lastEffect >= RATE_MS) play(kinds.get(id) ?? "hand");
      } else if (d.kind === "giant_leave") {
        giants.delete(String(d.id));
        sync();
      }
    }),
    // Safety net: if a giant_leave is ever lost, vision.state still tells us who is in view.
    // A giant missing from vision.state for LOST_MS is dropped (short flickers are ignored).
    hub.sub("vision.state", (env) => {
      const list = env.data?.giants;
      if (!Array.isArray(list)) return;
      const t = now();
      for (const g of list) {
        kinds.set(String(g.id), g.kind);
        lastSeen.set(String(g.id), t);
      }
      let changed = false;
      for (const id of [...giants]) {
        if (t - (lastSeen.get(id) ?? t) > LOST_MS) { giants.delete(id); changed = true; }
      }
      if (changed) sync();
    }),
    hub.sub("system.reset", clearAll),
  ];

  return {
    root,
    destroy() {
      clearTimeout(shakeTimer);
      offs.forEach((off) => typeof off === "function" && off());
      stage.classList.remove("giant-shake");
      root.remove();
    },
  };
}
