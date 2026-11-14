// Status and control page (T97, whitepaper §7.15). For the team during the demo.
//
//   system.health  -> services table (ok / stale / not ok, last seen); brain.<module> rows nest under brain
//   every topic    -> message rate per topic over the last 5 s
//   buttons        -> system.reset, world.select {name}, fake world.event, narration.say, sound.mute
//
// Every message this page publishes is shown in the log (↑); control-type messages published by others
// (resets, world selects, world events, narration) are shown as they arrive (↓).

import { connectHub } from "../common/hub.js";

const SRC = "status";
const RATE_WINDOW_MS = 5000;
const STALE_MS = 6000;           // services report every 2 s
const LOG_SIZE = 200;
const TEST_ID = 9999;            // object id used by the fake events, far from real tracker ids

// The 8 pre-composed worlds (whitepaper §7.6, T75). `name` is what world.select carries; the label is read
// from shared/worlds/<name>.json when that file exists.
const FALLBACK_WORLDS = [
  { name: "ocean", label: "Open ocean" },
  { name: "volcano", label: "Volcanic wasteland" },
  { name: "snow", label: "Snowy night village" },
  { name: "kingdom", label: "Kingdom" },
  { name: "neon", label: "Neon city" },
  { name: "rainforest", label: "Rainforest" },
  { name: "court", label: "Royal court" },
  { name: "space", label: "Space station" },
];

const FAKE_EVENTS = {
  giant_enter: { kind: "giant_enter", id: "g-test", giant_kind: "hand", edge: "top" },
  giant_leave: { kind: "giant_leave", id: "g-test" },
  danger_enter: { kind: "danger_enter", id: TEST_ID, name: "the Test Dragon", role: "dragon" },
  danger_exit: { kind: "danger_exit", id: TEST_ID },
  object_added: {
    kind: "object_added", id: TEST_ID, role: "dragon", name: "the Test Dragon", behaviour: "threat",
    announce: "A test dragon drops from the sky!", from_sky: true,
  },
};

const LOGGED_IN = (t) => t === "system.reset" || t === "world.select" || t === "world.event"
  || t === "narration.say" || t === "sound.mute" || t === "world.transition";

const $ = (id) => document.getElementById(id);
function el(tag, props = {}, ...kids) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...kids);
  return node;
}

let hub = null;
let muted = false;
let currentWorld = null;

// ---- message log -------------------------------------------------------------------------------------
const logEntries = [];
function log(dir, topic, data) {
  const time = new Date().toLocaleTimeString([], { hour12: false });
  logEntries.unshift({ time, dir, topic, data: JSON.stringify(data) });
  logEntries.length = Math.min(logEntries.length, LOG_SIZE);
  $("log").replaceChildren(...logEntries.map((e) => el("li", {},
    el("span", { className: "t", textContent: e.time }),
    el("span", { className: `dir ${e.dir}`, textContent: e.dir === "out" ? "↑" : "↓" }),
    el("span", { className: "k", textContent: e.topic }),
    el("span", { className: "d", textContent: e.data }),
  )));
}

function publish(topic, data) {
  log("out", topic, data);
  if (!hub) return;
  hub.pub(topic, data);
}

// ---- services ----------------------------------------------------------------------------------------
const services = new Map(); // service -> {ok, detail, seen}

function onHealth(env) {
  const d = env.data || {};
  if (typeof d.service !== "string") return;
  services.set(d.service, { ok: !!d.ok, detail: String(d.detail ?? ""), seen: Date.now() });
}

function ago(ms) {
  if (ms < 1000) return "now";
  if (ms < 60000) return `${Math.round(ms / 1000)} s`;
  return `${Math.round(ms / 60000)} min`;
}

function renderServices() {
  const now = Date.now();
  const names = [...services.keys()].sort((a, b) => {
    const [ra, rb] = [a.split(".")[0], b.split(".")[0]];
    return ra === rb ? (a.includes(".") - b.includes(".")) || a.localeCompare(b) : ra.localeCompare(rb);
  });
  if (!names.length) return;
  let ok = 0, bad = 0;
  const rows = names.map((name) => {
    const s = services.get(name);
    const age = now - s.seen;
    const state = age > STALE_MS ? "stale" : s.ok ? "ok" : "bad";
    if (state === "ok") ok++; else bad++;
    const label = state === "stale" ? "stale" : s.ok ? "ok" : "not ok";
    return el("tr", { className: name.includes(".") ? "sub" : "" },
      el("td", { textContent: name.includes(".") ? name.slice(name.indexOf(".") + 1) : name }),
      el("td", {}, el("span", { className: `pill ${state}`, textContent: label })),
      el("td", { className: "num", textContent: ago(age) }),
      el("td", { className: "detail", textContent: s.detail }),
    );
  });
  $("services").replaceChildren(...rows);
  $("svc-summary").textContent = `${ok} ok · ${bad} need attention`;
}

// ---- message rates -----------------------------------------------------------------------------------
const arrivals = new Map(); // topic -> [ms timestamps]

function countMessage(topic) {
  let list = arrivals.get(topic);
  if (!list) arrivals.set(topic, (list = []));
  list.push(performance.now());
}

function renderRates() {
  const now = performance.now();
  const topics = [...arrivals.keys()].sort();
  if (!topics.length) return;
  $("rates").replaceChildren(...topics.map((topic) => {
    const list = arrivals.get(topic);
    const last = list[list.length - 1];
    while (list.length && now - list[0] > RATE_WINDOW_MS) list.shift();
    const rate = list.length / (RATE_WINDOW_MS / 1000);
    return el("tr", {},
      el("td", { textContent: topic }),
      el("td", { className: "num", textContent: rate ? rate.toFixed(1) : "0" }),
      el("td", { className: "num", textContent: ago(now - last) }),
    );
  }));
}

// ---- world buttons -----------------------------------------------------------------------------------
async function buildWorldButtons() {
  const box = $("worlds");
  box.replaceChildren(...FALLBACK_WORLDS.map((w) => {
    const b = el("button", { type: "button", textContent: w.label, title: `world.select {name: "${w.name}"}` });
    b.dataset.world = w.name;
    b.addEventListener("click", () => publish("world.select", { name: w.name }));
    return b;
  }));
  // Use the real world names once the fallback world files (T75) are there.
  await Promise.all(FALLBACK_WORLDS.map(async (w) => {
    try {
      const res = await fetch(`/shared/worlds/${w.name}.json`);
      if (!res.ok) return;
      const world = await res.json();
      const name = world?.world?.name;
      const b = box.querySelector(`[data-world="${w.name}"]`);
      if (name && b) { w.worldName = name; b.textContent = name; }
    } catch { /* file not there yet: keep the default label */ }
  }));
  markCurrentWorld();
}

function markCurrentWorld() {
  const name = currentWorld?.world?.name;
  for (const b of $("worlds").querySelectorAll("button")) {
    const w = FALLBACK_WORLDS.find((x) => x.name === b.dataset.world);
    b.classList.toggle("current", !!name && (w.worldName === name || w.label === name));
  }
  $("world").textContent = name ? `World: ${name}` : "No world yet";
}

// ---- wiring ------------------------------------------------------------------------------------------
function bindControls() {
  $("reset").addEventListener("click", () => {
    if (confirm("Reset the whole demo? Every module clears its state.")) publish("system.reset", {});
  });
  $("mute").addEventListener("click", () => {
    muted = !muted;
    $("mute").classList.toggle("on", muted);
    $("mute").textContent = muted ? "Sounds muted (click to unmute)" : "Mute sounds";
    publish("sound.mute", { muted });
  });
  for (const b of document.querySelectorAll("[data-fake]")) {
    b.addEventListener("click", () => publish("world.event", { ...FAKE_EVENTS[b.dataset.fake] }));
  }
  $("say-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = $("say-text").value.trim();
    if (!text) return;
    publish("narration.say", { text, priority: Number($("say-priority").value) });
    $("say-text").value = "";
  });
}

function setHubStatus(s) {
  $("hub-dot").classList.toggle("on", s === "open");
  $("hub-text").textContent = s === "open" ? "Hub connected" : "Hub disconnected, retrying…";
}

async function main() {
  bindControls();
  buildWorldButtons();
  setInterval(() => { renderServices(); renderRates(); }, 1000);
  hub = await connectHub(undefined, SRC);
  setHubStatus("open");
  hub.onStatus(setHubStatus);
  hub.sub("*", (env) => {
    countMessage(env.topic);
    if (env.topic === "system.health") onHealth(env);
    if (env.topic === "world.current") {
      const w = env.data?.world;
      if (w?.id !== currentWorld?.id) { currentWorld = w; markCurrentWorld(); }
    }
    if (LOGGED_IN(env.topic) && env.src !== SRC) log("in", env.topic, env.data);
  });
}

main().catch((e) => {
  console.error("[status]", e);
  $("hub-text").textContent = `Hub error: ${e.message}`;
});
