// Sound page (T81, whitepaper §7.1, §7.8, §7.11). Runs on the laptop, plays out of its speaker.
//
//   sfx.play {sound}          -> synthesised effect (sfx.js)
//   narration.speak {id,...}  -> tts.speak (T80), effects ducked 50 % meanwhile -> narration.done {id}
//
// Browsers only allow audio after a click, so nothing plays until "Start sound" is pressed. Until then
// narration.speak is answered with narration.done straight away so the narration queue (T79) never stalls.

import { connectHub } from "../common/hub.js";
import { createSfx, soundNames } from "./sfx.js";

const LOG_SIZE = 10;
const $ = (id) => document.getElementById(id);

// T80 may be missing on an old checkout: fall back to a silent stub that takes about as long as speech.
async function loadTts() {
  try {
    return (await import("./tts.js")).createTts();
  } catch (e) {
    console.warn("[sound] tts.js not loaded, narration will be silent:", e.message);
    let cancelNow = null;
    return {
      speak: ({ text = "" } = {}) => new Promise((resolve) => {
        const timer = setTimeout(resolve, Math.min(8000, (text.length / 15) * 1000));
        cancelNow = () => { clearTimeout(timer); resolve(); };
      }),
      cancel: () => cancelNow?.(),
    };
  }
}

// ---- event log -------------------------------------------------------------------------------------
const events = [];
function log(kind, detail) {
  const time = new Date().toLocaleTimeString([], { hour12: false });
  events.unshift({ time, kind, detail });
  events.length = Math.min(events.length, LOG_SIZE);
  const ul = $("log");
  ul.replaceChildren(...events.map((e) => {
    const li = document.createElement("li");
    for (const [cls, text] of [["t", e.time], ["k", e.kind], ["d", e.detail]]) {
      const span = document.createElement("span");
      span.className = cls;
      span.textContent = text;
      li.append(span);
    }
    return li;
  }));
}

function showSpeaking(text) {
  const el = $("speaking");
  el.textContent = text || "Silent";
  el.classList.toggle("idle", !text);
}

// ---- main ------------------------------------------------------------------------------------------
async function main() {
  const sfx = createSfx();
  const tts = await loadTts();
  let started = false;
  let hub = null;
  let speakingId = null;

  // Sound check pad: every effect, horns first so they are easy to compare.
  const names = soundNames().sort((a, b) => (b.startsWith("horn_") - a.startsWith("horn_")) || a.localeCompare(b));
  $("pad").replaceChildren(...names.map((name) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = name;
    if (name.startsWith("horn_")) b.className = "horn";
    b.addEventListener("click", async () => { await sfx.unlock(); sfx.play(name); });
    return b;
  }));

  async function start() {
    await sfx.unlock();
    started = true;
    const btn = $("start");
    btn.disabled = true;
    btn.textContent = "Sound on";
    sfx.play("chime");
    log("start", "audio unlocked");
  }
  $("start").addEventListener("click", start);

  async function speak({ id, text, voice }) {
    speakingId = id;
    showSpeaking(text);
    sfx.duck(true);
    try {
      await tts.speak({ id, text, voice });
    } catch (e) {
      console.warn("[sound] tts failed", e);
    }
    if (speakingId === id) { // a newer line may have taken over
      speakingId = null;
      sfx.duck(false);
      showSpeaking("");
    }
  }

  for (const btn of document.querySelectorAll(".tools button")) {
    btn.addEventListener("click", async () => {
      if (!started) await start();
      const voice = btn.dataset.voice;
      speak({ id: `test-${Date.now()}`, text: `The storm rolls in. This is the ${voice || "default"} voice.`, voice });
    });
  }

  // ---- hub -------------------------------------------------------------------------------------------
  hub = await connectHub(undefined, "sound");
  const setHub = (s) => {
    $("hub-dot").classList.toggle("on", s === "open");
    $("hub-text").textContent = s === "open" ? "Hub connected" : "Hub offline";
  };
  setHub("open");
  hub.onStatus(setHub);

  hub.sub("sfx.play", ({ data }) => {
    const name = data?.sound;
    if (!started) { log("sfx (muted)", String(name)); return; }
    const played = sfx.play(name);
    log("sfx", played === name ? String(name) : `${name} → ${played ?? "failed"}`);
  });

  hub.sub("narration.speak", async ({ data }) => {
    const { id, text = "", voice } = data || {};
    if (!started) {
      log("speak (muted)", text);
      hub.pub("narration.done", { id });
      return;
    }
    log("speak", voice ? `[${voice}] ${text}` : text);
    await speak({ id, text, voice });
    hub.pub("narration.done", { id });
  });

  hub.sub("world.current", ({ data }) => {
    const name = data?.world?.world?.name;
    if (name) $("world").textContent = name;
  });

  hub.sub("system.reset", () => {
    tts.cancel();
    speakingId = null;
    sfx.duck(false);
    showSpeaking("");
    log("reset", "");
  });
}

main().catch((e) => {
  console.error("[sound] failed to start", e);
  $("hub-text").textContent = `Error: ${e.message}`;
});
