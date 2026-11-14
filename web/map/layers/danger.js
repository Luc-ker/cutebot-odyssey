// Danger layer (T90, whitepaper §7.11, §7.13): a glowing red/orange zone around every threat, so players can
// see where not to drive.
//
// The radius is exactly the one the danger detector (T57) uses: config DANGER_RADIUS plus half the object's
// size, in normalised table units. Distances are measured in normalised units on both axes, so on a
// non-square table the zone is an ellipse on screen, matching the detector. The glow breathes with the
// beat, brightens while the robot is inside, and flares briefly on `danger_enter`.

const DEFAULT_RADIUS = 0.12;
const FLARE_S = 1.2;

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export function zoneRadius(obj, dangerRadius = DEFAULT_RADIUS) {
  const size = Array.isArray(obj?.size) ? Math.max(obj.size[0] || 0, obj.size[1] || 0) : 0;
  return dangerRadius + size / 2;
}

export function createLayer() {
  let threats = [];
  let robot = null;
  let radius = DEFAULT_RADIUS;
  let lastEventSeq = 0;
  const flares = new Map(); // object id -> local time (s) of danger_enter

  return {
    update(state) {
      radius = Number(state.config?.DANGER_RADIUS) > 0 ? Number(state.config.DANGER_RADIUS) : DEFAULT_RADIUS;
      const objs = state["world.objects"]?.objects;
      threats = Array.isArray(objs) ? objs.filter((o) => o.behaviour === "threat" && Array.isArray(o.pos)) : [];
      const rs = state["robot.state"];
      robot = rs && rs.seen !== false && Array.isArray(rs.pos) ? rs.pos : null;
      for (const e of state.events ?? []) {
        if (e._seq <= lastEventSeq) continue;
        lastEventSeq = e._seq;
        if (e.kind === "danger_enter") flares.set(e.id, e._t);
      }
    },

    draw(ctx, rect, t, beat) {
      for (const o of threats) {
        const r = zoneRadius(o, radius);
        const inside = robot && Math.hypot(robot[0] - o.pos[0], robot[1] - o.pos[1]) < r;
        const flareAt = flares.get(o.id);
        const flare = flareAt !== undefined ? clamp(1 - (t - flareAt) / FLARE_S, 0, 1) : 0;
        const breathe = 1 + 0.05 * beat + 0.025 * Math.sin(t * 2.2 + Number(o.id || 0));
        const strength = clamp((inside ? 0.75 : 0.4) + 0.2 * beat + 0.5 * flare, 0, 1);

        const cx = rect.x + o.pos[0] * rect.w;
        const cy = rect.y + o.pos[1] * rect.h;
        ctx.save();
        ctx.translate(cx, cy);
        ctx.scale(r * rect.w * breathe, r * rect.h * breathe); // unit circle → the detector's ellipse
        const g = ctx.createRadialGradient(0, 0, 0, 0, 0, 1);
        g.addColorStop(0, `rgba(255,70,30,${0.45 * strength})`);
        g.addColorStop(0.6, `rgba(255,120,30,${0.28 * strength})`);
        g.addColorStop(0.92, `rgba(255,60,20,${0.4 * strength})`);
        g.addColorStop(1, "rgba(255,60,20,0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(0, 0, 1, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        // dashed boundary at the true radius, so the edge is unambiguous
        ctx.strokeStyle = `rgba(255,90,50,${0.35 + 0.4 * strength})`;
        ctx.lineWidth = inside ? 2.5 : 1.5;
        ctx.setLineDash([6, 6]);
        ctx.lineDashOffset = -t * 12;
        ctx.beginPath();
        ctx.ellipse(cx, cy, r * rect.w, r * rect.h, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
      }
      for (const [id, at] of flares) if (t - at > FLARE_S) flares.delete(id);
    },
  };
}
