// Giants layer (T91, whitepaper §7.10, §7.13): when a hand or a person leans over the table, a huge soft
// shadow falls across the map from that side, with a giant's hand icon where a hand reaches in.
//
// Input: vision.state.giants [{id, kind: "hand"|"person", pos, size, edge: "top"|"bottom"|"left"|"right"}].
// Each giant's shadow runs from its edge of the table (and beyond it) over its footprint; it eases in when it
// appears, follows the hand, and fades out after it leaves.

const FADE_IN_S = 0.45;
const FADE_OUT_S = 0.7;
const EASE_RATE = 9;
const HAND_ICON = new URL("../icons/giant_hand.svg", import.meta.url);

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

let handImg = null;
function loadHand() {
  if (handImg !== null || typeof Image === "undefined") return;
  handImg = undefined;
  fetch(HAND_ICON).then((r) => (r.ok ? r.text() : null)).then((text) => {
    if (!text) return;
    const img = new Image();
    img.onload = () => { handImg = img; };
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(text.replaceAll("currentColor", "rgb(40,30,40)"))}`;
  }).catch(() => {});
}

/** Pure: the shadow's arm as a polygon in table units, from the giant's edge to the far side of its footprint. */
export function shadowShape(g) {
  const [x, y] = g.pos;
  const [w, h] = g.size ?? [0.12, 0.12];
  const person = g.kind === "person";
  const spread = person ? 1.8 : 1.15; // a person's shoulders are wider than a hand's wrist
  switch (g.edge) {
    case "bottom": return { reach: [x, y - h / 2], base: [x, 1.08], halfW: (w / 2) * spread, axis: "y" };
    case "left": return { reach: [x + w / 2, y], base: [-0.08, y], halfW: (h / 2) * spread, axis: "x" };
    case "right": return { reach: [x - w / 2, y], base: [1.08, y], halfW: (h / 2) * spread, axis: "x" };
    default: return { reach: [x, y + h / 2], base: [x, -0.08], halfW: (w / 2) * spread, axis: "y" };
  }
}

export function createLayer() {
  loadHand();
  const shown = new Map(); // id -> {g, x, y, w, h, born, gone}
  let giants = [];
  let lastT = null;

  return {
    update(state) {
      const list = state["vision.state"]?.giants;
      giants = Array.isArray(list) ? list.filter((g) => Array.isArray(g.pos)) : [];
    },

    draw(ctx, rect, t) {
      const dt = lastT === null ? 0 : clamp(t - lastT, 0, 0.25);
      lastT = t;
      const live = new Set();
      for (const g of giants) {
        const id = String(g.id ?? `${g.edge}-${g.kind}`);
        live.add(id);
        let s = shown.get(id);
        if (!s) {
          s = { x: g.pos[0], y: g.pos[1], born: t, gone: null };
          shown.set(id, s);
        }
        s.g = g;
        s.gone = null;
      }
      const k = 1 - Math.exp(-EASE_RATE * dt);
      const unit = rect.unit ?? rect.h / 600;

      for (const [id, s] of shown) {
        if (!live.has(id) && s.gone === null) s.gone = t;
        let alpha = clamp((t - s.born) / FADE_IN_S, 0, 1);
        if (s.gone !== null) alpha *= clamp(1 - (t - s.gone) / FADE_OUT_S, 0, 1);
        if (s.gone !== null && alpha <= 0) { shown.delete(id); continue; }
        if (s.gone === null) {
          s.x += (s.g.pos[0] - s.x) * k;
          s.y += (s.g.pos[1] - s.y) * k;
        }
        const g = { ...s.g, pos: [s.x, s.y] };
        const sh = shadowShape(g);
        const P = ([u, v]) => [rect.x + u * rect.w, rect.y + v * rect.h];
        const [rx, ry] = P(sh.reach);
        const [bx, by] = P(sh.base);
        const half = sh.halfW * (sh.axis === "y" ? rect.w : rect.h);
        const tip = half * (g.kind === "person" ? 1.1 : 1.35);

        ctx.save();
        ctx.globalAlpha = 0.55 * alpha;
        if ("filter" in ctx) ctx.filter = `blur(${Math.round(14 * unit)}px)`;
        ctx.fillStyle = "rgb(10,6,14)";
        ctx.beginPath();
        if (sh.axis === "y") {
          ctx.moveTo(bx - half * 1.3, by);
          ctx.lineTo(rx - half, ry);
          ctx.lineTo(rx + half, ry);
          ctx.lineTo(bx + half * 1.3, by);
        } else {
          ctx.moveTo(bx, by - half * 1.3);
          ctx.lineTo(rx, ry - half);
          ctx.lineTo(rx, ry + half);
          ctx.lineTo(bx, by + half * 1.3);
        }
        ctx.closePath();
        ctx.fill();
        ctx.beginPath(); // the palm / head at the reaching end
        ctx.arc(rx, ry, tip, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        if (g.kind !== "person" && handImg) {
          const size = tip * 2.2;
          const rot = { top: Math.PI, bottom: 0, left: Math.PI / 2, right: -Math.PI / 2 }[g.edge] ?? Math.PI;
          ctx.save();
          ctx.globalAlpha = 0.6 * alpha;
          ctx.translate(rx, ry);
          ctx.rotate(rot);
          ctx.drawImage(handImg, -size / 2, -size * 0.55, size, size);
          ctx.restore();
        }
      }
    },
  };
}
