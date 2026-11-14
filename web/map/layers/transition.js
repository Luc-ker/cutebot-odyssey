// Transition layer (T94, whitepaper §7.12): when the world changes, the old map is wiped away by an expanding
// circle centred on the robot, revealing the new world underneath, with a sparkle burst on each object as the
// wipe front passes it. One module, two slots (see map.js):
//
//   drawUnder  (after terrain)  a band of light on the new ground just behind the wipe front
//   drawOver   (last)           the old world's picture outside the circle, the glowing front, sparkles
//
// The "old world's picture": world.current switches before world.transition arrives (T95 reacts to it), so
// grabbing the canvas at transition start would already show the new world. Instead this layer keeps a rolling
// snapshot of the finished frame every SNAP_EVERY_S, tagged with the world it showed, and keeps the last
// snapshot of the previous world when the world id changes. The wipe uses the snapshot of `from`.

const SNAP_EVERY_S = 0.2;
const DEFAULT_MS = 3000;
const SPARKS_PER_OBJECT = 16;
const SPARK_LIFE_S = 0.9;

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const easeInOut = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);

function makeCanvas(w, h) {
  if (typeof OffscreenCanvas !== "undefined") return new OffscreenCanvas(w, h);
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  return c;
}

/** Pure: wipe radius in px at progress p (0..1) for a centre and a view size. */
export function wipeRadius(p, cx, cy, viewW, viewH) {
  const far = Math.max(Math.hypot(cx, cy), Math.hypot(viewW - cx, cy), Math.hypot(cx, viewH - cy), Math.hypot(viewW - cx, viewH - cy));
  return easeInOut(clamp(p, 0, 1)) * far * 1.02;
}

export function createLayer() {
  // rolling snapshots: `cur` is the latest frame of the current world, `prev` the last frame of the one before
  let snaps = { cur: { id: null, canvas: null, at: -Infinity }, prev: { id: null, canvas: null, at: -Infinity } };
  let worldId = null;
  let robotPos = null;
  let objects = [];
  let accent = [255, 230, 160];

  let seenSeq = 0;
  let active = null; // {start, dur, from, snapshot, centre, passed:Set, sparks:[]}
  let pendingStart = null;

  function capture(ctx, t) {
    const src = ctx.canvas;
    if (!src?.width) return;
    if (snaps.cur.id !== worldId && snaps.cur.canvas) {
      snaps = { cur: snaps.prev, prev: snaps.cur }; // keep the old world's last frame
      snaps.cur.id = null;
    }
    const c = snaps.cur;
    if (!c.canvas || c.canvas.width !== src.width || c.canvas.height !== src.height) c.canvas = makeCanvas(src.width, src.height);
    const g = c.canvas.getContext("2d");
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, src.width, src.height);
    g.drawImage(src, 0, 0);
    c.id = worldId;
    c.at = t;
  }

  function snapshotFor(fromId) {
    if (fromId && snaps.prev.id === fromId) return snaps.prev.canvas;
    if (fromId && snaps.cur.id === fromId) return snaps.cur.canvas;
    return snaps.prev.canvas ?? null; // best effort: the previous world, whatever it was
  }

  function centre(rect) {
    if (robotPos) return [rect.x + robotPos[0] * rect.w, rect.y + robotPos[1] * rect.h];
    return [rect.x + rect.w / 2, rect.y + rect.h / 2];
  }

  return {
    update(state) {
      worldId = state["world.current"]?.world?.id ?? null;
      const rs = state["robot.state"];
      if (rs && Array.isArray(rs.pos)) robotPos = rs.pos;
      const objs = state["world.objects"]?.objects;
      objects = Array.isArray(objs) ? objs.filter((o) => Array.isArray(o.pos)) : [];
      if (Array.isArray(state.palette?.[2])) accent = state.palette[2];
      const tr = state.transition;
      if (!tr) { active = null; pendingStart = null; return; } // reset
      if (tr._seq > seenSeq) {
        seenSeq = tr._seq;
        if (tr.from) pendingStart = { start: tr._t, dur: (Number(tr.duration_ms) > 0 ? Number(tr.duration_ms) : DEFAULT_MS) / 1000, fromId: tr.from.id };
      }
    },

    drawUnder(ctx, rect, t) {
      if (!active) return;
      const p = (t - active.start) / active.dur;
      if (p >= 1) return;
      const [cx, cy] = active.centre;
      const r = wipeRadius(p, cx, cy, rect.viewW, rect.viewH);
      const band = 90 * (rect.unit ?? 1);
      const inner = Math.max(0, r - band);
      const g = ctx.createRadialGradient(cx, cy, inner, cx, cy, r);
      g.addColorStop(0, `rgba(${accent[0]},${accent[1]},${accent[2]},0)`);
      g.addColorStop(1, `rgba(${accent[0]},${accent[1]},${accent[2]},0.35)`);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();
    },

    drawOver(ctx, rect, t) {
      if (pendingStart) {
        const snapshot = snapshotFor(pendingStart.fromId);
        active = snapshot ? { ...pendingStart, snapshot, centre: centre(rect), passed: new Set(), sparks: [] } : null;
        pendingStart = null;
      }

      if (active) {
        const p = (t - active.start) / active.dur;
        const sparksLeft = active.sparks.some((s) => t - s.born < SPARK_LIFE_S);
        if (p >= 1 && !sparksLeft) {
          active = null;
        } else {
          const [cx, cy] = active.centre;
          const r = wipeRadius(p, cx, cy, rect.viewW, rect.viewH);
          if (p < 1) {
            // the old world, outside the circle
            ctx.save();
            ctx.beginPath();
            ctx.rect(0, 0, rect.viewW, rect.viewH);
            ctx.arc(cx, cy, Math.max(0.1, r), 0, Math.PI * 2, true);
            ctx.clip("evenodd");
            ctx.drawImage(active.snapshot, 0, 0, rect.viewW, rect.viewH);
            ctx.restore();
            // the glowing front
            const unit = rect.unit ?? 1;
            ctx.strokeStyle = `rgba(${accent[0]},${accent[1]},${accent[2]},0.9)`;
            ctx.lineWidth = 4 * unit + 2;
            ctx.shadowColor = `rgba(${accent[0]},${accent[1]},${accent[2]},1)`;
            ctx.shadowBlur = 24 * unit;
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, Math.PI * 2);
            ctx.stroke();
            ctx.shadowBlur = 0;
          }
          // sparkle bursts as the front passes each object
          for (const o of objects) {
            if (active.passed.has(o.id)) continue;
            const ox = rect.x + o.pos[0] * rect.w;
            const oy = rect.y + o.pos[1] * rect.h;
            if (Math.hypot(ox - cx, oy - cy) > r) continue;
            active.passed.add(o.id);
            for (let i = 0; i < SPARKS_PER_OBJECT; i++) {
              const an = (i / SPARKS_PER_OBJECT) * Math.PI * 2 + Math.random() * 0.4;
              const sp = (60 + Math.random() * 90) * (rect.unit ?? 1);
              active.sparks.push({ x: ox, y: oy, vx: Math.cos(an) * sp, vy: Math.sin(an) * sp - 30, born: t, s: 2 + Math.random() * 3 });
            }
          }
          ctx.save();
          ctx.globalCompositeOperation = "lighter";
          for (const s of active.sparks) {
            const age = t - s.born;
            if (age < 0 || age > SPARK_LIFE_S) continue;
            const k = 1 - age / SPARK_LIFE_S;
            const x = s.x + s.vx * age;
            const y = s.y + s.vy * age + 40 * age * age;
            const size = s.s * (0.5 + k);
            ctx.fillStyle = `rgba(255,${200 + 55 * k},${140 + 100 * k},${k})`;
            ctx.beginPath(); // four-point star
            ctx.moveTo(x, y - size * 2);
            ctx.lineTo(x + size * 0.5, y - size * 0.5);
            ctx.lineTo(x + size * 2, y);
            ctx.lineTo(x + size * 0.5, y + size * 0.5);
            ctx.lineTo(x, y + size * 2);
            ctx.lineTo(x - size * 0.5, y + size * 0.5);
            ctx.lineTo(x - size * 2, y);
            ctx.lineTo(x - size * 0.5, y - size * 0.5);
            ctx.closePath();
            ctx.fill();
          }
          ctx.restore();
          active.sparks = active.sparks.filter((s) => t - s.born <= SPARK_LIFE_S);
        }
      }

      // keep the rolling snapshot fresh while no wipe is running
      if (!active && t - snaps.cur.at >= SNAP_EVERY_S) capture(ctx, t);
      else if (!active && snaps.cur.id !== worldId) capture(ctx, t);
    },
  };
}
