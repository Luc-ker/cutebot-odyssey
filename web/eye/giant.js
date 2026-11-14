// Giant arrival effect on the robot's-eye view (T35, whitepaper §7.10).
// world.event giant_enter: the top of the screen darkens, a shadow sweeps down, the view shakes and a
// caption names a colossus suited to the world ("A frost giant reaches down from the sky").
// giant_leave (last giant gone): the shadow lifts. At most one effect every 4 s; more enters in that
// window keep the shadow but don't replay the effect.

const RATE_MS = 4000;
const CAPTION_MS = 3500;
const SHAKE_MS = 600;
const LOST_MS = 2000;

const GIANTS = [
  [["sea", "ocean", "water", "island", "harbour", "reef", "coast"], "sea god"],
  [["snow", "ice", "frost", "frozen", "winter", "glacier", "tundra"], "frost giant"],
  [["volcan", "lava", "fire", "ash", "wasteland", "desert", "inferno"], "fire giant"],
  [["neon", "city", "cyber", "future", "space", "metropolis"], "colossal mech"],
  [["jungle", "forest", "swamp", "grove", "woods"], "forest giant"],
  [["kingdom", "castle", "royal", "medieval", "court", "village"], "stone titan"],
];

/** Pure: the colossus for a world (C4), e.g. "frost giant". */
export function giantName(world) {
  const info = world?.world ?? {};
  const text = `${info.setting ?? ""} ${info.name ?? ""}`.toLowerCase();
  for (const [keys, name] of GIANTS) if (keys.some((k) => text.includes(k))) return name;
  return "giant";
}

/** Pure: the caption for a giant of `kind` ("hand" | "person") in `world`. */
export function giantCaption(world, kind = "hand") {
  const name = giantName(world);
  const article = /^[aeiou]/.test(name) ? "An" : "A";
  return kind === "person"
    ? `${article} ${name} looms over the world`
    : `${article} ${name} reaches down from the sky`;
}

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
  root.innerHTML = '<div class="giant-shadow"></div><div class="giant-caption"></div>';
  container.append(root);
  const shadow = root.querySelector(".giant-shadow");
  const caption = root.querySelector(".giant-caption");
  const stage = container.closest?.(".stage") ?? container.parentElement ?? doc.body;
  const reduced = () => Boolean(globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches);

  let world = null;
  const giants = new Set();
  const lastSeen = new Map(); // giant id -> time last confirmed by an event or vision.state
  const kinds = new Map(); // giant id -> "hand" | "person", from vision.state
  let lastEffect = -Infinity;
  let captionTimer = null;
  let shakeTimer = null;

  function play(kind) {
    lastEffect = now();
    // Restart the sweep animation even if the class is already there.
    shadow.classList.remove("sweep");
    void shadow.offsetWidth;
    shadow.classList.add("sweep");

    caption.textContent = giantCaption(world, kind);
    caption.classList.add("visible");
    clearTimeout(captionTimer);
    captionTimer = setTimeout(() => caption.classList.remove("visible"), CAPTION_MS);

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
    caption.classList.remove("visible");
    stage.classList.remove("giant-shake");
  }

  const offs = [
    hub.sub("world.current", (env) => { world = env.data?.world ?? world; }),
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
    // Safety net: if a giant_leave is ever lost, the overhead view still tells us who is there.
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
      clearTimeout(captionTimer);
      clearTimeout(shakeTimer);
      offs.forEach((off) => typeof off === "function" && off());
      stage.classList.remove("giant-shake");
      root.remove();
    },
  };
}
