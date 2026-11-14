// Overhead map shell (T85, whitepaper §7.13, §4): the second screen, a full-screen canvas that draws the
// table as a living fantasy map from stacked layers.
//
// Each frame: compute the table rect (aspect from TABLE_W_CM / TABLE_H_CM), work out the beat envelope
// (beat.js, T93, or 0), then call every layer's update(state) and draw(ctx, rect, t, beat) in this order:
//
//   terrain, transition-under, danger, objects, robot, giants, info, transition-over
//
// Layers are loaded with dynamic import(); a missing layer is skipped, and a throwing layer only loses that
// frame (with a rate-limited console warning). The transition layer (T94) is one module that fills both
// transition slots: drawUnder() in the first, drawOver() (or draw()) in the second.
//
// `rect` is {x, y, w, h} for the table in CSS pixels plus {viewW, viewH} (the whole canvas) and `unit`
// (a size scale, 1 at a ~600 px tall table). `state` is the store (store.js) plus `state.palette`
// ([[r,g,b] x3], the current world's palette resolved through shared/colours.json) and `state.palettes`
// ({worldId: palette}) so a transition can still tint the old world.
//
// `?demo` runs a self-contained demo (fake worlds, objects, robot, beat and giants) with no hardware;
// `?demo=3` holds fallback world 3 instead of cycling.

import { connectHub } from "../common/hub.js";
import { createStore } from "./store.js";

const SLOTS = [
  ["terrain", "./layers/terrain.js"],
  ["transition-under", "./layers/transition.js"],
  ["danger", "./layers/danger.js"],
  ["objects", "./layers/objects.js"],
  ["robot", "./layers/robot.js"],
  ["giants", "./layers/giants.js"],
  ["info", "./layers/info.js"],
  ["transition-over", "./layers/transition.js"],
];
const TOPICS = ["world.*", "robot.state", "vision.state", "audio.*", "system.*", "video.status"];
const WARN_EVERY = 600; // frames between repeated warnings for the same broken layer
const DEFAULT_PALETTE = [[70, 90, 120], [200, 170, 110], [230, 225, 210]];

const canvas = document.getElementById("map");
const ctx = canvas.getContext("2d");
const now = () => performance.now() / 1000;

// ---- config, store, palette --------------------------------------------------------------------------

async function loadConfig() {
  try {
    return await (await import("../common/config.js")).loadConfig();
  } catch (e) {
    console.warn("[map] config not loaded, using defaults:", e.message);
    return {};
  }
}

let colourFor = null;
async function resolvePalette(world) {
  const words = world?.world?.palette;
  if (!Array.isArray(words) || !words.length) return DEFAULT_PALETTE;
  try {
    colourFor ??= (await import("../common/colours.js")).colourFor;
    const out = await Promise.all(words.slice(0, 3).map((w) => colourFor(w)));
    while (out.length < 3) out.push(DEFAULT_PALETTE[out.length]);
    return out;
  } catch {
    return DEFAULT_PALETTE;
  }
}

function trackPalettes(store) {
  const { state } = store;
  state.palette = DEFAULT_PALETTE;
  state.palettes = {};
  const pending = new Set();
  const want = (world) => {
    const id = world?.id;
    if (!id || state.palettes[id] || pending.has(id)) return;
    pending.add(id);
    resolvePalette(world).then((p) => {
      pending.delete(id);
      state.palettes[id] = p;
    });
  };
  const apply = store.apply;
  store.apply = (env) => {
    apply(env);
    if (env?.topic === "world.current") want(env.data?.world);
    if (env?.topic === "world.transition") { want(env.data?.from); want(env.data?.to); }
    if (env?.topic === "system.reset") { state.palette = DEFAULT_PALETTE; state.palettes = {}; }
  };
  return () => {
    const id = state["world.current"]?.world?.id;
    state.palette = (id && state.palettes[id]) || state.palette || DEFAULT_PALETTE;
  };
}

// ---- layers ----------------------------------------------------------------------------------------------

async function loadLayers() {
  const modules = new Map();
  for (const [, path] of SLOTS) {
    if (modules.has(path)) continue;
    try {
      const mod = await import(path);
      const layer = mod.createLayer();
      modules.set(path, { path, layer, errors: 0 });
    } catch (e) {
      console.warn(`[map] layer ${path} not loaded:`, e.message);
      modules.set(path, null);
    }
  }
  return SLOTS.map(([slot, path]) => {
    const entry = modules.get(path);
    if (!entry) return null;
    const { layer } = entry;
    let draw = layer.draw?.bind(layer);
    if (slot === "transition-under") draw = layer.drawUnder?.bind(layer);
    if (slot === "transition-over") draw = (layer.drawOver ?? layer.draw)?.bind(layer);
    return draw ? { slot, entry, draw } : null;
  }).filter(Boolean);
}

function guard(entry, what, fn) {
  try {
    fn();
  } catch (e) {
    if (entry.errors % WARN_EVERY === 0) console.warn(`[map] layer ${entry.path} ${what} failed:`, e);
    entry.errors += 1;
  }
}

// ---- geometry ----------------------------------------------------------------------------------------------

function tableRect(viewW, viewH, aspect) {
  const margin = Math.max(24, Math.min(viewW, viewH) * 0.07); // room for "the edge of the world"
  const aw = viewW - margin * 2;
  const ah = viewH - margin * 2;
  let w = aw;
  let h = aw / aspect;
  if (h > ah) { h = ah; w = ah * aspect; }
  return { x: (viewW - w) / 2, y: (viewH - h) / 2, w, h, viewW, viewH, unit: h / 600 };
}

function resize() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = Math.round(window.innerWidth * dpr);
  const h = Math.round(window.innerHeight * dpr);
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  return dpr;
}

function drawBase(rect) {
  ctx.fillStyle = "#0b0a09";
  ctx.fillRect(0, 0, rect.viewW, rect.viewH);
  ctx.fillStyle = "#1b1915";
  ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
  ctx.strokeStyle = "rgba(240, 225, 190, 0.55)";
  ctx.lineWidth = 2;
  ctx.setLineDash([10, 8]);
  ctx.strokeRect(rect.x, rect.y, rect.w, rect.h);
  ctx.setLineDash([]);
}

// ---- main ----------------------------------------------------------------------------------------------------

async function main() {
  const config = await loadConfig();
  const aspect = (config.TABLE_W_CM > 0 && config.TABLE_H_CM > 0) ? config.TABLE_W_CM / config.TABLE_H_CM : 1.5;
  const store = createStore({ now, config });
  const syncPalette = trackPalettes(store);

  let beatFn = null;
  try {
    beatFn = (await import("./beat.js")).beatFromState;
  } catch (e) {
    console.warn("[map] beat.js not loaded, beat = 0:", e.message);
  }

  const layers = await loadLayers();
  const updaters = [...new Set(layers.map((l) => l.entry))];

  const params = new URLSearchParams(location.search);
  if (params.has("demo")) {
    demo(store, config, params.get("demo"));
  } else {
    connectHub(undefined, "map").then((hub) => {
      const conn = document.getElementById("conn");
      hub.onStatus?.((s) => { conn.hidden = s === "open"; });
      for (const t of TOPICS) hub.sub(t, store.apply);
    }).catch((e) => console.warn("[map] hub connect failed:", e));
  }

  window.addEventListener("keydown", (e) => {
    if (e.key === "f" || e.key === "F") {
      if (document.fullscreenElement) document.exitFullscreen();
      else document.documentElement.requestFullscreen?.();
    }
  });

  function frame() {
    const dpr = resize();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const rect = tableRect(canvas.width / dpr, canvas.height / dpr, aspect);
    const t = now();
    let beat = 0;
    if (beatFn) {
      try { beat = beatFn(store.state, t) || 0; } catch { beat = 0; }
    }
    syncPalette();
    drawBase(rect);
    for (const entry of updaters) {
      if (entry.layer.update) guard(entry, "update", () => entry.layer.update(store.state));
    }
    for (const l of layers) {
      ctx.save();
      guard(l.entry, `draw (${l.slot})`, () => l.draw(ctx, rect, t, beat));
      ctx.restore();
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

// ---- demo mode (?demo) ------------------------------------------------------------------------------------------
// A self-running stand-in for the hub so the map can be checked without the robot, Jetson or Gemini.

const DEMO_WORLDS = [
  ["The Drowned Kingdom", "stormy open ocean", "brooding", "dusk", "rain", ["ocean blue", "storm grey", "lantern gold"], "open sea",
    [["ship", "the Gull", "neutral"], ["sea_serpent", "the Coil", "threat"], ["lighthouse", "the Old Lamp", "friendly"], ["island", "Palm Key", "friendly"], ["harbour", "Saltmarsh", "friendly"], ["shipwreck", "the Wreck", "neutral"]]],
  ["The Ember Wastes", "volcanic wasteland", "furious", "night", "ash fall", ["lava red", "volcanic black", "ember orange"], "cracked basalt",
    [["fortress", "Blackspire", "neutral"], ["lava_beast", "Cinderjaw", "threat"], ["camp", "Last Camp", "friendly"], ["volcano", "Mount Rage", "neutral"], ["ash_field", "the Grey Reach", "neutral"], ["lava_cave", "the Maw", "neutral"]]],
  ["Frostholm", "snowy night village", "hushed", "night", "snowfall", ["midnight blue", "snow white", "candle yellow"], "deep snow",
    [["watchtower", "the Lookout", "friendly"], ["yeti", "Old Shaggy", "threat"], ["snow_cottage", "Hearthome", "friendly"], ["mountain", "the Tooth", "neutral"], ["glacier", "the Blue Wall", "neutral"], ["den", "the Bear's Den", "neutral"]]],
  ["The Amber Realm", "medieval kingdom", "heroic", "noon", "clear", ["forest green", "pale gold", "ivory"], "rolling meadows",
    [["castle", "Highkeep", "neutral"], ["dragon", "Emberwing", "threat"], ["village", "Millbrook", "friendly"], ["forest", "the Old Wood", "neutral"], ["road", "the King's Road", "neutral"], ["bridge", "Stonearch", "neutral"]]],
  ["Neon Sprawl", "neon city", "electric", "night", "drizzle", ["neon pink", "electric blue", "cyber yellow"], "wet asphalt",
    [["skyscraper", "Arc Tower", "neutral"], ["robot_sentinel", "Unit Nine", "threat"], ["neon_arcade", "Pixel Palace", "friendly"], ["subway", "Line Zero", "neutral"], ["drone_swarm", "the Hive", "threat"], ["road", "Route 66", "neutral"]]],
  ["The Green Deep", "rainforest", "mysterious", "dawn", "mist", ["jungle green", "emerald", "sulfur yellow"], "tangled undergrowth",
    [["temple", "Sun Temple", "neutral"], ["jaguar", "Shadowpaw", "threat"], ["ruin", "the Lost Stair", "neutral"], ["jungle_patch", "the Thicket", "neutral"], ["river", "the Serpent River", "neutral"], ["relic", "the Idol", "friendly"]]],
  ["Court of Strings", "royal court", "graceful", "evening", "still", ["royal purple", "pale gold", "pearl"], "marble halls",
    [["palace", "the Grand Palace", "neutral"], ["throne_room", "the Throne", "friendly"], ["catacombs", "the Crypts", "neutral"], ["grove", "Queen's Garden", "neutral"], ["market", "the Bazaar", "friendly"], ["wolf_pack", "the Hounds", "threat"]]],
  ["Station Lumen", "space station", "dreamy", "eternal night", "starfield", ["deep purple", "electric blue", "moonlight silver"], "open vacuum",
    [["docking_tower", "Dock Seven", "friendly"], ["asteroid", "the Rock", "threat"], ["engine_room", "the Core", "neutral"], ["observatory", "Starglass", "friendly"], ["crystal", "Power Crystals", "friendly"], ["drone_swarm", "Scrap Drones", "threat"]]],
];
const DEMO_OBJECTS = [
  { id: 1, cls: "chair", pos: [0.22, 0.30], size: [0.12, 0.14] },
  { id: 2, cls: "scissors", pos: [0.72, 0.28], size: [0.07, 0.06] },
  { id: 3, cls: "bottle", pos: [0.50, 0.70], size: [0.05, 0.08] },
  { id: 4, cls: "bowl", pos: [0.82, 0.72], size: [0.09, 0.09] },
  { id: 5, cls: "book", pos: [0.18, 0.75], size: [0.10, 0.07] },
  { id: 6, cls: "box", pos: [0.25, 0.80], size: [0.07, 0.07] },
];
const DEMO_TEMPOS = [104, 140, 72, 96, 118, 128, 88, 80];
const SKY_ROLE = { role: "treasure", name: "a fallen chest", behaviour: "friendly" };

function demoWorld(i) {
  const [name, setting, mood, time_of_day, weather, palette, open_space, roles] = DEMO_WORLDS[i];
  return {
    id: `w-0000000${i}`,
    world: { name, setting, mood, time_of_day, weather, palette },
    roles: roles.map(([role, rname, behaviour], k) => ({ object_id: DEMO_OBJECTS[k].id, role, name: rname, behaviour })),
    terrain: { open_space, under_table: "the deep" },
    restyle_prompt: "", narration: `Welcome to ${name}.`,
    music_signature: { tempo_bpm: DEMO_TEMPOS[i], energy: 0.6, brightness: 0.5, chroma: [] },
  };
}

function demo(store, config, arg) {
  const hold = arg !== null && arg !== "" && Number.isFinite(Number(arg));
  let wi = hold ? Math.max(0, Math.min(7, Number(arg))) % 8 : 0;
  let world = demoWorld(wi);
  const send = (topic, data) => store.apply({ topic, ts: Date.now() / 1000, src: "demo", data });
  const t0 = now();
  let lastBeat = 0;
  let skyUntil = -1;
  let lastSky = 0;
  let inDanger = new Set();
  let overrideUntil = 0;
  let lastGiant = -1;

  send("world.current", { world, previous_id: null });
  send("world.event", { kind: "world_changed", world_id: world.id, returning: false });

  const objectsFor = (t) => {
    const objs = DEMO_OBJECTS.map((o, k) => {
      const r = world.roles[k];
      // object 3 drifts slowly so the smoothing is visible
      const pos = o.id === 3 ? [0.5 + 0.08 * Math.sin(t / 3), 0.7 + 0.04 * Math.cos(t / 4)] : o.pos;
      return { id: o.id, cls: o.cls, pos, size: o.size, role: r.role, name: r.name, behaviour: r.behaviour, cluster_id: null, from_sky: false };
    });
    if (t < skyUntil) objs.push({ id: 99, cls: "box", pos: [0.62, 0.45], size: [0.07, 0.07], ...SKY_ROLE, cluster_id: null, from_sky: true });
    // objects 5 and 6 are close together: one cluster ("place")
    objs[4].cluster_id = "c1";
    objs[5].cluster_id = "c1";
    const clusters = [{ id: "c1", pos: [0.215, 0.775], member_ids: [5, 6], role: "village", name: "Twin Hamlets" }];
    return { world_id: world.id, objects: objs, clusters,
      terrain: { open_regions: [{ x: 0.35, y: 0.1, w: 0.3, h: 0.3 }], open_space: world.terrain.open_space, under_table: "the deep" } };
  };

  function tick() {
    const t = now() - t0;
    // world change every 14 s
    if (!hold && t > 2 && Math.floor(t / 14) !== Math.floor((t - 0.1) / 14)) {
      const from = world;
      wi = (wi + 1) % 8;
      world = demoWorld(wi);
      send("world.current", { world, previous_id: from.id });
      setTimeout(() => {
        send("world.transition", { from, to: world, started: Date.now() / 1000, duration_ms: config.TRANSITION_MS || 3000 });
        send("world.event", { kind: "world_changed", world_id: world.id, returning: false });
      }, 80);
    }
    // beat
    const period = 60 / DEMO_TEMPOS[wi];
    if (t - lastBeat >= period) {
      lastBeat = t;
      send("audio.beat", { tempo_bpm: DEMO_TEMPOS[wi], strength: 0.8 });
    }
    const silent = (t % 40) > 36; // a short silence every 40 s
    send("audio.features", { rms: 0.2, energy: 0.5 + 0.4 * Math.sin(t / 5), brightness: 0.5, silent });
    // object dropped from the sky every 25 s, gone 9 s later
    if (t - lastSky > 25) {
      lastSky = t;
      skyUntil = t + 9;
      send("world.event", { kind: "object_added", id: 99, ...SKY_ROLE, announce: "", from_sky: true });
    }
    const objects = objectsFor(t);
    send("world.objects", objects);
    // robot on a loop; lost from 20-23 s every 30 s
    const a = t * 0.35;
    const pos = [0.5 + 0.33 * Math.sin(a), 0.5 + 0.3 * Math.sin(2 * a)];
    const vel = [0.33 * Math.cos(a), 0.6 * Math.cos(2 * a)];
    const heading = Math.atan2(vel[1], vel[0]);
    const seen = !((t % 30) > 20 && (t % 30) < 23);
    const radius = config.DANGER_RADIUS ?? 0.12;
    for (const o of objects.objects) {
      if (o.behaviour !== "threat") continue;
      const d = Math.hypot(o.pos[0] - pos[0], o.pos[1] - pos[1]);
      if (d < radius + Math.max(...o.size) / 2 && !inDanger.has(o.id) && seen) {
        inDanger.add(o.id);
        overrideUntil = t + 0.8;
        send("world.event", { kind: "danger_enter", id: o.id, name: o.name, role: o.role });
      } else if (d > (radius + Math.max(...o.size) / 2) * 1.2 && inDanger.has(o.id)) {
        inDanger.delete(o.id);
        send("world.event", { kind: "danger_exit", id: o.id });
      }
    }
    send("robot.state", { pos, heading, seen, distance_cm: 50, override: t < overrideUntil, facing_id: null });
    // a giant every 15 s for 5 s, from a rotating edge
    const gPhase = t % 15;
    const giants = [];
    if (gPhase > 6 && gPhase < 11) {
      const k = Math.floor(t / 15) % 4;
      const edge = ["top", "right", "bottom", "left"][k];
      const reach = Math.min(1, (gPhase - 6) / 1.2) * 0.25;
      const gp = { top: [0.6, reach], right: [1 - reach, 0.4], bottom: [0.35, 1 - reach], left: [reach, 0.55] }[edge];
      giants.push({ id: `g${Math.floor(t / 15)}`, kind: k === 3 ? "person" : "hand", pos: gp, size: [0.14, 0.18], edge });
      if (lastGiant !== Math.floor(t / 15)) {
        lastGiant = Math.floor(t / 15);
        send("world.event", { kind: "giant_enter", id: giants[0].id, edge });
      }
    }
    send("vision.state", { frame_ts: Date.now() / 1000, objects: [], robot: { pos, heading, seen }, giants });
    // health
    if (Math.floor(t * 10) % 20 === 0) {
      for (const [service, ok] of [["jetson", true], ["gemini", (t % 50) < 40], ["eye", true], ["serial_bridge", true]]) {
        send("system.health", { service, ok, detail: ok ? "" : "timeout" });
      }
    }
  }
  setInterval(tick, 100);
  tick();
}

main().catch((e) => console.error("[map] failed to start", e));
