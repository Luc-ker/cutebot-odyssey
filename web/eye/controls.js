// Show controls on the robot's-eye page: two quiet buttons in the bottom-right corner.
//   show   — start / stop the show: AI video plus music-driven scene changes (Space)
//   listen — listen to the song now (M): one listening window, then one new scene for it; pressing
//            again while it listens cancels. Hidden when the brain has no microphone
// The brain owns the state: a press publishes `show.set`, and the buttons only change when
// `show.state` comes back, so every open eye page agrees. The cluster rests almost invisible and
// wakes (with the mouse pointer) while the mouse moves.

const WAKE_MS = 2600;

function ensureCss(doc, href) {
  if (!doc.head?.querySelector || doc.head.querySelector(`link[href="${href}"]`)) return;
  const link = doc.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  doc.head.append(link);
}

/** Pure: the state the next press asks for. Exported for tests. */
export function nextShowSet(state, which) {
  return which === "show" ? { running: !state.running } : { listening: !state.listening };
}

/**
 * @param {HTMLElement} container  where the cluster goes (the eye page's .stage)
 * @param {{sub: Function, pub: Function}} hub
 * @param {object} [opts]  onState(state) callback; test seams: setTimeout, clearTimeout, keyTarget
 */
export function mountControls(container, hub, opts = {}) {
  const doc = container.ownerDocument ?? globalThis.document;
  const setT = opts.setTimeout ?? globalThis.setTimeout.bind(globalThis);
  const clearT = opts.clearTimeout ?? globalThis.clearTimeout.bind(globalThis);
  const keyTarget = opts.keyTarget ?? doc;
  try { ensureCss(doc, new URL("./controls.css", import.meta.url).href); } catch { /* non-browser */ }

  const root = doc.createElement("div");
  root.className = "controls";
  root.setAttribute("role", "group");
  root.setAttribute("aria-label", "Show controls");

  const button = (which, label, title) => {
    const b = doc.createElement("button");
    b.type = "button";
    b.className = `ctl ctl-${which}`;
    b.title = title;
    b.setAttribute("aria-pressed", "true");
    const glyph = doc.createElement("span");
    glyph.className = "ctl-glyph";
    glyph.setAttribute("aria-hidden", "true");
    if (which === "listen") {
      for (let i = 0; i < 3; i++) { const bar = doc.createElement("i"); glyph.append(bar); }
    }
    const text = doc.createElement("span");
    text.className = "ctl-label";
    text.textContent = label;
    b.append(glyph, text);
    b.addEventListener("click", () => press(which));
    return b;
  };
  const show = button("show", "show", "Start or stop the show · Space");
  const listen = button("listen", "listen", "Listen to the song now and change the scene · M");
  root.append(show, listen);
  container.append(root);

  // Until the brain answers, assume the defaults it starts with.
  let state = { running: true, listening: false, can_listen: true };
  let known = false;

  function draw() {
    show.setAttribute("aria-pressed", String(state.running));
    listen.setAttribute("aria-pressed", String(state.listening && state.running));
    listen.hidden = !state.can_listen;
    listen.disabled = !state.running;
    root.classList.toggle("known", known);
  }

  function press(which) {
    if (which === "listen" && (!state.can_listen || !state.running)) return;
    hub.pub("show.set", nextShowSet(state, which));
  }

  let wakeTimer = null;
  const wake = () => {
    doc.body?.classList.add("awake");
    if (wakeTimer) clearT(wakeTimer);
    wakeTimer = setT(() => { wakeTimer = null; doc.body?.classList.remove("awake"); }, WAKE_MS);
  };
  const onKey = (e) => {
    if (e.repeat || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === " ") { e.preventDefault?.(); wake(); press("show"); }
    else if (e.key?.toLowerCase() === "m") { wake(); press("listen"); }
  };
  doc.addEventListener?.("mousemove", wake);
  keyTarget.addEventListener?.("keydown", onKey);

  const off = hub.sub("show.state", (env) => {
    const d = env.data ?? {};
    state = { running: d.running !== false, listening: d.listening === true, can_listen: d.can_listen !== false };
    known = true;
    draw();
    opts.onState?.(state);
  });
  draw();
  hub.pub("show.set", {}); // an empty set asks the brain to send show.state right away

  return {
    root,
    get state() { return { ...state }; },
    press,
    destroy() {
      if (typeof off === "function") off();
      if (wakeTimer) clearT(wakeTimer);
      doc.removeEventListener?.("mousemove", wake);
      keyTarget.removeEventListener?.("keydown", onKey);
      root.remove?.();
    },
  };
}
