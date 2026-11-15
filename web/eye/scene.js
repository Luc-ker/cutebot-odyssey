// Scene model for the local renderer (docs/local-renderer.md): what to draw where, on every video frame.
//
//   const scene = createScene({ fallbackRole });
//   scene.onVision(visionState, receivedAt)   // `vision.state` (C3), with optional outline / client_ts
//   scene.onObjects(worldObjects, receivedAt) // `world.objects`: the role each object id plays
//   scene.items(t)  -> [{id, cls, role, behaviour, box:{x1,y1,x2,y2}, outline, alpha, appear, seed}]
//
// Vision arrives ~10 times a second and 100–250 ms late; video arrives 30 times a second. So for every
// video frame each object's box is *predicted* to time `t` from its last measurements (constant velocity,
// measured on the eye page's own clock via `client_ts`), then smoothed with a One Euro filter so the
// graphic neither jitters when still nor lags when the robot turns. Everything is in view units (0..1).
// Outlines are stored relative to their box, so they move and scale with the predicted box.
//
// Pure: no DOM. `t` and `receivedAt` are milliseconds on one clock (performance.now in the page).

export const HOLD_MS = 350;        // keep drawing an object this long after vision stops reporting it
export const FADE_OUT_MS = 250;    // then fade it out over this long
export const APPEAR_MS = 450;      // a newly assigned role grows into place over this long
export const MAX_PREDICT_MS = 300; // never extrapolate further than this past the last measurement
export const DEFAULT_LATENCY_MS = 150; // assumed vision age until client_ts lets us measure it
export const ROLES_STALE_MS = 2000; // world.objects silent this long -> use fallbackRole(cls)

const VEL_BLEND = 0.5;  // new velocity estimate weight
const MIN_CUTOFF = 1.2; // One Euro: Hz, smoothing when still
const BETA = 0.015;     // One Euro: how fast smoothing relaxes with speed (per view-unit/s)
const D_CUTOFF = 1.0;

/** One Euro filter (Casiez et al. 2012) on one value; `t` in ms. */
export function oneEuro({ minCutoff = MIN_CUTOFF, beta = BETA, dCutoff = D_CUTOFF } = {}) {
  let x = null, dx = 0, last = null;
  const alpha = (cutoff, dt) => 1 / (1 + 1 / (2 * Math.PI * cutoff * dt));
  return {
    filter(value, t) {
      if (x === null || last === null || t <= last) { x = value; last = t; return value; }
      const dt = (t - last) / 1000;
      last = t;
      const rawDx = (value - x) / dt;
      dx += alpha(dCutoff, dt) * (rawDx - dx);
      const cutoff = minCutoff + beta * Math.abs(dx) * 1000;
      x += alpha(cutoff, dt) * (value - x);
      return x;
    },
    reset() { x = null; last = null; dx = 0; },
  };
}

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const easeOut = (k) => 1 - (1 - k) ** 3;

/** Pure: a view-unit outline -> points relative to box {x1,y1,x2,y2} (0..1 inside the box). */
export function outlineToBox(outline, box) {
  if (!Array.isArray(outline) || outline.length < 3) return null;
  const w = Math.max(box.x2 - box.x1, 1e-6), h = Math.max(box.y2 - box.y1, 1e-6);
  return outline.map(([x, y]) => [(x - box.x1) / w, (y - box.y1) / h]);
}

function hashSeed(id) {
  let h = 2166136261;
  for (const ch of String(id)) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return ((h >>> 0) % 10000) / 10000;
}

/**
 * @param {object} [o]
 * @param {(cls: string) => ({role, behaviour}|null)} [o.fallbackRole]  roles when world.objects is silent
 */
export function createScene(o = {}) {
  const fallbackRole = o.fallbackRole ?? (() => null);
  const tracks = new Map(); // id -> track
  let roles = new Map();    // id -> {role, behaviour, name}
  let rolesAt = -Infinity;
  let latency = null;       // smoothed age of vision states, ms

  function track(id, cls) {
    let tr = tracks.get(id);
    if (!tr) {
      tr = {
        id, cls, m: null, v: [0, 0, 0, 0], sampleT: null, lastSeen: -Infinity,
        outline: null, roleKey: null, appearAt: null, seed: hashSeed(id),
        filters: [oneEuro(), oneEuro(), oneEuro(), oneEuro()],
      };
      tracks.set(id, tr);
    }
    tr.cls = cls ?? tr.cls;
    return tr;
  }

  function roleFor(tr, t) {
    const r = roles.get(tr.id);
    if (r?.role) return r;
    if (t - rolesAt > ROLES_STALE_MS) return fallbackRole(tr.cls) ?? null;
    return null;
  }

  return {
    /** `vision.state` data; `receivedAt` = clock time it arrived. */
    onVision(data, receivedAt) {
      const objects = Array.isArray(data?.objects) ? data.objects : [];
      // When was this frame grabbed, on our clock? client_ts says exactly; otherwise assume a typical age.
      let sampleT = receivedAt - (latency ?? DEFAULT_LATENCY_MS);
      if (Number.isFinite(data?.client_ts) && data.client_ts <= receivedAt + 5) {
        const age = receivedAt - data.client_ts;
        latency = latency === null ? age : latency * 0.8 + age * 0.2;
        sampleT = data.client_ts;
      }
      for (const ob of objects) {
        if (!Number.isInteger(ob?.id) || !Array.isArray(ob.pos) || !Array.isArray(ob.size)) continue;
        const tr = track(ob.id, ob.cls);
        const m = [ob.pos[0], ob.pos[1], ob.size[0], ob.size[1]];
        if (tr.m && tr.sampleT !== null && sampleT > tr.sampleT && receivedAt - tr.lastSeen < 1000) {
          const dt = sampleT - tr.sampleT;
          const est = m.map((v, i) => (v - tr.m[i]) / dt);
          tr.v = tr.v.map((v, i) => v * (1 - VEL_BLEND) + est[i] * VEL_BLEND);
        } else if (receivedAt - tr.lastSeen >= 1000) {
          tr.v = [0, 0, 0, 0];
          tr.filters.forEach((f) => f.reset());
        }
        tr.m = m;
        tr.sampleT = sampleT;
        tr.lastSeen = receivedAt;
        const box = { x1: m[0] - m[2] / 2, y1: m[1] - m[3] / 2, x2: m[0] + m[2] / 2, y2: m[1] + m[3] / 2 };
        const rel = outlineToBox(ob.outline, box);
        if (rel) tr.outline = rel;
      }
    },

    /** `world.objects` data: which role each id plays (null until assigned). */
    onObjects(data, receivedAt) {
      const next = new Map();
      for (const ob of Array.isArray(data?.objects) ? data.objects : []) {
        if (Number.isInteger(ob?.id) && ob.role) next.set(ob.id, { role: ob.role, behaviour: ob.behaviour ?? null, name: ob.name ?? null });
      }
      roles = next;
      rolesAt = receivedAt;
    },

    reset() { tracks.clear(); roles = new Map(); rolesAt = -Infinity; },

    /** Smoothed vision age in ms, or null before client_ts has been seen. */
    get latencyMs() { return latency; },

    /** What to draw at time `t`, farthest (highest on screen) first. */
    items(t) {
      const out = [];
      for (const tr of tracks.values()) {
        const since = t - tr.lastSeen;
        if (!tr.m || since > HOLD_MS + FADE_OUT_MS) {
          if (since > 5000) tracks.delete(tr.id);
          continue;
        }
        const r = roleFor(tr, t);
        const key = r ? r.role : null;
        if (key !== tr.roleKey) { tr.roleKey = key; tr.appearAt = key ? t : null; }
        if (!key) continue;

        // Predict to now, but only as far as MAX_PREDICT_MS past the measurement (one vision age plus
        // one update interval); once vision has gone quiet, hold that spot instead of drifting off.
        const ahead = clamp(t - tr.sampleT, 0, MAX_PREDICT_MS);
        const p = tr.m.map((v, i) => v + tr.v[i] * ahead);
        const [cx, cy, w, h] = p.map((v, i) => tr.filters[i].filter(v, t));
        const ww = Math.max(w, 0.005), hh = Math.max(h, 0.005);

        const appear = tr.appearAt === null ? 1 : easeOut(clamp((t - tr.appearAt) / APPEAR_MS, 0, 1));
        const fade = since <= HOLD_MS ? 1 : 1 - clamp((since - HOLD_MS) / FADE_OUT_MS, 0, 1);
        out.push({
          id: tr.id, cls: tr.cls, role: key, behaviour: r.behaviour ?? null, name: r.name ?? null,
          box: { x1: cx - ww / 2, y1: cy - hh / 2, x2: cx + ww / 2, y2: cy + hh / 2 },
          outline: tr.outline, alpha: clamp(appear * fade, 0, 1), appear, seed: tr.seed,
        });
      }
      return out.sort((a, b) => a.box.y2 - b.box.y2);
    },
  };
}
