// Info layer (T92, whitepaper §7.13): a corner panel with the current world's name (large), its
// setting · mood · weather (small), the music's tempo with a note that pulses on the beat ("listening…"
// when silent), and tiny health dots for Jetson, Gemini, video and bridge.
//
// Health comes from system.health (the store keeps one entry per service); a service is matched to a dot by
// name, and goes grey when it hasn't reported for 6 s. The video dot also accepts video.status.

const STALE_S = 6;
const NO_BEAT_S = 4; // no beat for this long → "listening…"
const DOTS = [
  ["Jetson", ["jetson", "vision", "camera", "tracker"]],
  ["Gemini", ["gemini", "composer", "world"]],
  ["Video", ["video", "eye", "restyle", "phone"]],
  ["Bridge", ["bridge", "serial", "radio", "microbit"]],
];

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

/** Pure: {label: "ok" | "bad" | "unknown"} from store health ({service: {ok, _t}}) at time `now`. */
export function healthDots(health = {}, now = 0, videoStatus = null, videoT = null) {
  const out = {};
  for (const [label, keys] of DOTS) {
    let status = "unknown";
    let newest = -Infinity;
    for (const [service, h] of Object.entries(health)) {
      const name = service.toLowerCase();
      if (!keys.some((k) => name.includes(k))) continue;
      if (now - h._t > STALE_S || h._t < newest) continue;
      newest = h._t;
      status = h.ok ? "ok" : "bad";
    }
    if (label === "Video" && status === "unknown" && videoStatus && videoT !== null && now - videoT <= STALE_S) {
      status = videoStatus.mode === "restyled" ? "ok" : "bad";
    }
    out[label] = status;
  }
  return out;
}

function fit(ctx, text, maxW) {
  if (ctx.measureText(text).width <= maxW) return text;
  let s = text;
  while (s.length > 1 && ctx.measureText(`${s}…`).width > maxW) s = s.slice(0, -1);
  return `${s}…`;
}

export function createLayer() {
  let world = null;
  let tempo = null;
  let silent = false;
  let lastBeatT = null;
  let health = {};
  let video = null;
  let videoT = null;

  return {
    update(state) {
      world = state["world.current"]?.world?.world ?? null;
      tempo = state["audio.beat"]?.tempo_bpm ?? null;
      silent = Boolean(state["audio.features"]?.silent);
      lastBeatT = state.lastBeatT ?? null;
      health = state.health ?? {};
      video = state["video.status"] ?? null;
      videoT = state.received?.["video.status"] ?? null;
    },

    draw(ctx, rect, t, beat) {
      const u = clamp(rect.unit ?? rect.h / 600, 0.75, 1.6);
      const pad = 14 * u;
      const w = 300 * u;
      const h = 132 * u;
      const x = 16;
      const y = 16;

      ctx.fillStyle = "rgba(14,10,8,0.72)";
      ctx.strokeStyle = "rgba(240,215,160,0.35)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect?.(x, y, w, h, 12 * u) ?? ctx.rect(x, y, w, h);
      ctx.fill();
      ctx.stroke();

      ctx.textAlign = "left";
      ctx.textBaseline = "alphabetic";
      const inner = w - pad * 2;

      // world name
      ctx.fillStyle = "#fbf1d6";
      const title = world?.name || "Awaiting a world…";
      let px = Math.round(24 * u); // shrink long names before truncating them
      ctx.font = `700 ${px}px Georgia, "Times New Roman", serif`;
      while (px > 15 * u && ctx.measureText(title).width > inner) {
        px -= 1;
        ctx.font = `700 ${px}px Georgia, "Times New Roman", serif`;
      }
      ctx.fillText(fit(ctx, title, inner), x + pad, y + pad + 22 * u);

      // setting · mood · weather
      const sub = [world?.setting, world?.mood, world?.weather].filter(Boolean).join(" · ");
      ctx.fillStyle = "rgba(240,225,190,0.75)";
      ctx.font = `${Math.round(13 * u)}px ui-sans-serif, system-ui, sans-serif`;
      ctx.fillText(fit(ctx, sub || "—", inner), x + pad, y + pad + 42 * u);

      // tempo with a pulsing note
      const listening = silent || !tempo || lastBeatT === null || t - lastBeatT > NO_BEAT_S;
      const ny = y + pad + 72 * u;
      const scale = 1 + 0.35 * beat;
      ctx.save();
      ctx.translate(x + pad + 9 * u, ny - 6 * u);
      ctx.scale(scale, scale);
      ctx.fillStyle = listening ? "rgba(240,225,190,0.4)" : `rgba(255,${200 - 60 * beat},${90 - 60 * beat},1)`;
      ctx.font = `${Math.round(22 * u)}px "Apple Symbols", "Segoe UI Symbol", serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("♪", 0, 0);
      ctx.restore();
      ctx.textAlign = "left";
      ctx.font = `600 ${Math.round(16 * u)}px ui-sans-serif, system-ui, sans-serif`;
      ctx.fillStyle = listening ? "rgba(240,225,190,0.6)" : "#fbf1d6";
      ctx.fillText(listening ? "listening…" : `${Math.round(tempo)} bpm`, x + pad + 24 * u, ny);

      // health dots, on their own row
      const dots = healthDots(health, t, video, videoT);
      const hy = y + pad + 102 * u;
      ctx.font = `${Math.round(11.5 * u)}px ui-sans-serif, system-ui, sans-serif`;
      ctx.textAlign = "left";
      let dx = x + pad;
      for (const [label] of DOTS) {
        const status = dots[label];
        ctx.fillStyle = status === "ok" ? "#7fd36a" : status === "bad" ? "#e5533d" : "#6b655c";
        ctx.beginPath();
        ctx.arc(dx + 4 * u, hy - 4 * u, 4 * u, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "rgba(240,225,190,0.7)";
        ctx.fillText(label, dx + 12 * u, hy);
        dx += 12 * u + ctx.measureText(label).width + 16 * u;
      }
    },
  };
}
