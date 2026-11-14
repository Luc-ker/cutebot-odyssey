// Robot layer (T89, whitepaper §7.13, §7.15): the player as a small explorer marker with a heading arrow and
// a fading trail of the last ~15 s.
//
// - Position and heading ease toward each robot.state, so the marker glides rather than ticks.
// - `seen: false` (the overhead camera lost it): the marker freezes where it was, greyed, with a "?".
//   It never jumps; when the robot is found again it glides from the frozen spot.
// - `override: true` (recoil in progress): the marker flashes red.

const TRAIL_S = 15;
const TRAIL_STEP_S = 0.1;
const EASE_RATE = 10;
const RED = [230, 60, 45];

const rgba = (c, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

function angleLerp(a, b, k) {
  let d = b - a;
  while (d > Math.PI) d -= 2 * Math.PI;
  while (d < -Math.PI) d += 2 * Math.PI;
  return a + d * k;
}

export function createLayer() {
  let target = null;   // latest robot.state with a pos
  let seen = false;
  let override = false;
  let shown = null;    // {x, y, heading}
  let lastT = null;
  let lastTrailAt = -Infinity;
  const trail = [];    // {x, y, t}

  return {
    update(state) {
      const rs = state["robot.state"];
      if (!rs) { // nothing yet, or cleared by system.reset
        target = null;
        shown = null;
        trail.length = 0;
        return;
      }
      seen = rs.seen !== false && Array.isArray(rs.pos);
      override = Boolean(rs.override);
      if (seen) target = { x: rs.pos[0], y: rs.pos[1], heading: Number(rs.heading) || 0 };
    },

    draw(ctx, rect, t) {
      const dt = lastT === null ? 0 : clamp(t - lastT, 0, 0.25);
      lastT = t;
      if (!target) return;
      if (!shown) shown = { ...target };
      if (seen) { // when unseen, `shown` simply stays put
        const k = 1 - Math.exp(-EASE_RATE * dt);
        shown.x += (target.x - shown.x) * k;
        shown.y += (target.y - shown.y) * k;
        shown.heading = angleLerp(shown.heading, target.heading, k);
        if (t - lastTrailAt >= TRAIL_STEP_S) {
          trail.push({ x: shown.x, y: shown.y, t });
          lastTrailAt = t;
        }
      }
      while (trail.length && t - trail[0].t > TRAIL_S) trail.shift();

      const unit = rect.unit ?? rect.h / 600;
      const toPx = (p) => [rect.x + p.x * rect.w, rect.y + p.y * rect.h];

      // trail: dotted footsteps fading with age
      ctx.lineCap = "round";
      for (let i = 1; i < trail.length; i++) {
        const age = (t - trail[i].t) / TRAIL_S;
        const [x0, y0] = toPx(trail[i - 1]);
        const [x1, y1] = toPx(trail[i]);
        ctx.strokeStyle = `rgba(255,244,214,${0.55 * (1 - age)})`;
        ctx.lineWidth = Math.max(1.5, 4 * unit * (1 - age * 0.6));
        ctx.setLineDash([2, 7 * unit]);
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.stroke();
      }
      ctx.setLineDash([]);

      // the marker
      const [px, py] = toPx(shown);
      const r = 13 * unit + 4;
      const flash = override && Math.sin(t * 2 * Math.PI * 6) > 0;
      const body = !seen ? [150, 150, 150] : flash ? RED : [255, 236, 190];
      const edge = !seen ? [70, 70, 70] : [43, 29, 14];

      ctx.fillStyle = "rgba(0,0,0,0.3)";
      ctx.beginPath();
      ctx.ellipse(px, py + r * 0.7, r * 0.9, r * 0.35, 0, 0, Math.PI * 2);
      ctx.fill();

      if (seen) { // soft glow so it stands out on any terrain
        const g = ctx.createRadialGradient(px, py, r * 0.5, px, py, r * 2.4);
        g.addColorStop(0, rgba(flash ? RED : [255, 230, 160], 0.45));
        g.addColorStop(1, rgba([255, 230, 160], 0));
        ctx.fillStyle = g;
        ctx.fillRect(px - r * 2.4, py - r * 2.4, r * 4.8, r * 4.8);
      }

      ctx.save();
      ctx.translate(px, py);
      ctx.rotate(shown.heading);
      ctx.fillStyle = rgba(body);
      ctx.strokeStyle = rgba(edge);
      ctx.lineWidth = Math.max(2, 2.5 * unit);
      ctx.lineJoin = "round";
      ctx.beginPath();
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      // heading arrow
      ctx.fillStyle = rgba(!seen ? [110, 110, 110] : flash ? [255, 230, 220] : [214, 64, 40]);
      ctx.beginPath();
      ctx.moveTo(r * 1.65, 0);
      ctx.lineTo(r * 0.45, -r * 0.55);
      ctx.lineTo(r * 0.7, 0);
      ctx.lineTo(r * 0.45, r * 0.55);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();

      if (!seen) {
        ctx.fillStyle = "#2a2a2a";
        ctx.font = `700 ${Math.round(r * 1.2)}px Georgia, serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("?", px, py + 1);
      } else {
        ctx.fillStyle = rgba(edge);
        ctx.beginPath();
        ctx.arc(px, py, r * 0.28, 0, Math.PI * 2);
        ctx.fill();
      }
    },
  };
}
