// Objects layer (T87, whitepaper §7.13, §7.4, §7.5): every tracked object as an illustrated icon for its role,
// with its name, following the real object.
//
// - Icon from shared/roles.json (`role` → `icon`) at web/map/icons/<icon>.svg (T88), tinted with the world
//   palette; a lettered circle stands in while loading or if the file is missing.
// - Size from the object's footprint, clamped; name label underneath with a dark halo.
// - Threats get a red ring, friendlies a gold one; the object the robot faces gets a soft highlight.
// - Positions ease toward each update; icons bob with the beat.
// - `from_sky` objects drop in with a landing puff; removed objects fade out.
// - Clusters draw one place icon with the cluster's name; members are drawn smaller and unlabelled.

const ROLES_URL = new URL("../../shared/roles.json", import.meta.url);
const iconUrl = (icon) => new URL(`../icons/${icon}.svg`, import.meta.url);

const EASE_RATE = 8;          // 1/s, position smoothing
const FADE_IN_S = 0.4;
const FADE_OUT_S = 0.6;
const DROP_S = 0.75;
const RED = [226, 64, 48];
const GOLD = [240, 196, 74];
const CREAM = [250, 240, 214];

const rgba = (c, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
const mix = (p, q, k) => p.map((v, i) => Math.round(v + (q[i] - v) * k));
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

// ---- icons ----------------------------------------------------------------------------------------------

let roleIcons = null; // role -> icon
function loadRoles() {
  if (roleIcons) return;
  roleIcons = new Map();
  fetch(ROLES_URL).then((r) => (r.ok ? r.json() : [])).then((roles) => {
    for (const r of roles) if (r.role) roleIcons.set(r.role, r.icon || r.role);
  }).catch(() => {});
}
const iconFor = (role) => roleIcons?.get(role) ?? role ?? "unknown";

const svgText = new Map();   // icon -> Promise<string|null>
const images = new Map();    // icon|colour -> HTMLImageElement | "loading" | null

function tintedIcon(icon, colour) {
  const key = `${icon}|${colour}`;
  const hit = images.get(key);
  if (hit !== undefined) return hit === "loading" ? null : hit;
  images.set(key, "loading");
  if (!svgText.has(icon)) {
    svgText.set(icon, fetch(iconUrl(icon)).then((r) => (r.ok ? r.text() : null)).catch(() => null));
  }
  svgText.get(icon).then((text) => {
    if (!text || typeof Image === "undefined") { images.set(key, null); return; }
    const img = new Image();
    img.onload = () => images.set(key, img);
    img.onerror = () => images.set(key, null);
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(text.replaceAll("currentColor", colour))}`;
  });
  return null;
}

function letterCircle(ctx, x, y, size, role, fill) {
  ctx.fillStyle = fill;
  ctx.strokeStyle = "#2b1d0e";
  ctx.lineWidth = Math.max(1.5, size * 0.05);
  ctx.beginPath();
  ctx.arc(x, y, size * 0.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#2b1d0e";
  ctx.font = `700 ${Math.round(size * 0.42)}px Georgia, serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(String(role || "?").charAt(0).toUpperCase(), x, y + size * 0.02);
}

function label(ctx, text, x, y, px) {
  if (!text) return;
  ctx.font = `600 ${px}px Georgia, "Times New Roman", serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.lineJoin = "round";
  ctx.lineWidth = Math.max(3, px * 0.3);
  ctx.strokeStyle = "rgba(20,12,6,0.85)";
  ctx.strokeText(text, x, y);
  ctx.fillStyle = "#fbf3df";
  ctx.fillText(text, x, y);
}

// ---- the layer --------------------------------------------------------------------------------------------

export function createLayer() {
  loadRoles();
  const shown = new Map(); // key ("o<id>" | "c<id>") -> display record
  let objects = [];
  let clusters = [];
  let facingId = null;
  let palette = null;
  let lastT = null;
  let worldId = null;
  let firstUpdate = true;

  function track(key, target, t) {
    let rec = shown.get(key);
    if (!rec) {
      rec = { x: target.pos[0], y: target.pos[1], born: t, gone: null, sky: Boolean(target.from_sky) && !firstUpdate };
      shown.set(key, rec);
    }
    rec.target = target;
    rec.seenAt = t;
    rec.gone = null;
    return rec;
  }

  return {
    update(state) {
      const wo = state["world.objects"];
      const wid = state["world.current"]?.world?.id ?? null;
      if (wo && (!wid || !wo.world_id || wo.world_id === wid)) {
        objects = Array.isArray(wo.objects) ? wo.objects.filter((o) => Array.isArray(o.pos)) : [];
        clusters = Array.isArray(wo.clusters) ? wo.clusters.filter((c) => Array.isArray(c.pos)) : [];
      }
      if (wid !== worldId) worldId = wid;
      facingId = state["robot.state"]?.facing_id ?? null;
      palette = state.palette ?? null;
    },

    draw(ctx, rect, t, beat) {
      const dt = lastT === null ? 0 : clamp(t - lastT, 0, 0.25);
      lastT = t;
      const unit = rect.unit ?? rect.h / 600;
      const tint = palette?.[1] ? mix(palette[1], CREAM, 0.6) : CREAM;
      const tintStr = `rgb(${tint[0]},${tint[1]},${tint[2]})`;
      const minPx = 34 * unit;
      const maxPx = 92 * unit;
      const labelPx = Math.round(clamp(14 * unit, 11, 20));

      // mark what is present this frame
      const live = new Set();
      const inCluster = new Set();
      for (const c of clusters) for (const id of c.member_ids ?? []) inCluster.add(id);
      for (const o of objects) { track(`o${o.id}`, o, t); live.add(`o${o.id}`); }
      for (const c of clusters) {
        track(`c${c.id}`, { ...c, size: c.size ?? [0.12, 0.12], behaviour: c.behaviour ?? "neutral", cluster: true }, t);
        live.add(`c${c.id}`);
      }
      firstUpdate = false;
      for (const [key, rec] of shown) {
        if (!live.has(key) && rec.gone === null) rec.gone = t;
        if (rec.gone !== null && t - rec.gone > FADE_OUT_S) shown.delete(key);
      }

      // ease and sort by depth
      const k = 1 - Math.exp(-EASE_RATE * dt);
      const list = [...shown.entries()].map(([key, rec]) => {
        rec.x += (rec.target.pos[0] - rec.x) * k;
        rec.y += (rec.target.pos[1] - rec.y) * k;
        return [key, rec];
      }).sort((a, b) => a[1].y - b[1].y);

      for (const [key, rec] of list) {
        const o = rec.target;
        const isCluster = key.startsWith("c");
        const member = !isCluster && inCluster.has(o.id);
        const foot = Math.max((o.size?.[0] ?? 0.08) * rect.w, (o.size?.[1] ?? 0.08) * rect.h);
        let size = clamp(foot * 1.3, minPx, maxPx);
        if (member) size *= 0.6;
        if (isCluster) size = clamp(size * 1.15, minPx * 1.2, maxPx * 1.15);

        // alpha: fade in, fade out
        let alpha = rec.sky ? 1 : clamp((t - rec.born) / FADE_IN_S, 0, 1);
        if (rec.gone !== null) alpha *= clamp(1 - (t - rec.gone) / FADE_OUT_S, 0, 1);
        if (alpha <= 0) continue;

        let px = rect.x + rec.x * rect.w;
        let py = rect.y + rec.y * rect.h;
        // bob with the beat (alternate objects bob a little differently)
        py -= beat * 4 * unit * (Number(o.id) % 2 ? 1 : 0.7);

        // drop from the sky
        let scale = 1;
        if (rec.sky) {
          const e = clamp((t - rec.born) / DROP_S, 0, 1);
          const fall = (1 - e) * (1 - e);
          py -= fall * 160 * unit;
          scale = 1 + fall * 0.4;
          ctx.globalAlpha = 0.35 * e;
          ctx.fillStyle = "#000";
          ctx.beginPath();
          ctx.ellipse(px, rect.y + rec.y * rect.h + size * 0.4, size * 0.45 * e, size * 0.12 * e, 0, 0, Math.PI * 2);
          ctx.fill();
          const after = t - rec.born - DROP_S;
          if (after > 0 && after < 0.6) { // landing puff
            const p = after / 0.6;
            ctx.globalAlpha = (1 - p) * 0.8;
            ctx.strokeStyle = rgba(CREAM);
            ctx.lineWidth = 3 * unit;
            ctx.beginPath();
            ctx.ellipse(px, py + size * 0.4, size * (0.5 + p), size * (0.15 + p * 0.3), 0, 0, Math.PI * 2);
            ctx.stroke();
          }
        }
        const s = size * scale;
        ctx.globalAlpha = alpha;

        // behaviour ring and facing highlight
        const ring = o.behaviour === "threat" ? RED : o.behaviour === "friendly" ? GOLD : null;
        if (o.id === facingId && !isCluster) {
          ctx.fillStyle = rgba([255, 255, 230], 0.18 + 0.1 * Math.sin(t * 5));
          ctx.beginPath();
          ctx.arc(px, py, s * 0.62, 0, Math.PI * 2);
          ctx.fill();
        }
        if (ring && !member) {
          ctx.strokeStyle = rgba(ring, 0.9);
          ctx.lineWidth = Math.max(2, s * 0.06);
          ctx.beginPath();
          ctx.arc(px, py, s * 0.55, 0, Math.PI * 2);
          ctx.stroke();
          ctx.fillStyle = rgba(ring, 0.16);
          ctx.fill();
        }

        const icon = iconFor(o.role);
        const img = tintedIcon(icon, tintStr) ?? (icon !== "unknown" && images.get(`${icon}|${tintStr}`) === null
          ? tintedIcon("unknown", tintStr) : null);
        if (img) ctx.drawImage(img, px - s / 2, py - s / 2, s, s);
        else letterCircle(ctx, px, py, s, o.role, tintStr);

        if (!member) label(ctx, o.name || (o.role ?? "").replace(/_/g, " "), px, py + s * 0.5, isCluster ? labelPx + 2 : labelPx);
        ctx.globalAlpha = 1;
      }
    },
  };
}
