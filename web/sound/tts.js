// Text-to-speech for the narrator (T80, whitepaper §7.8, contract C9).
//
//   const tts = createTts();
//   await tts.speak({ id: "n1", text: "The storm rolls in.", voice: "old" });  // resolves on end or error
//   tts.cancel();                                                               // stops and resolves
//
// Uses the browser's speechSynthesis with an English voice. `voice` hints ("deep", "bright", "old",
// "robotic") pick a matching installed voice where one exists and always adjust pitch and rate.
// A server TTS can be plugged in (see HOOK below); it is off by default.

const CHARS_PER_S = 12;
const SAFETY_PAD_S = 5; // some browsers never fire onend; give up after len/12 + 5 s

// Name patterns are tried in order against the installed voices (macOS, Windows, Chrome, Android names).
export const VOICE_HINTS = {
  deep: {
    pitch: 0.7, rate: 0.9,
    prefer: [/\bdaniel\b/i, /\bdavid\b/i, /\bgeorge\b/i, /\barthur\b/i, /\bguy\b/i, /\bfred\b/i, /\balex\b/i, /\bmale\b/i],
  },
  bright: {
    pitch: 1.3, rate: 1.05,
    prefer: [/\bsamantha\b/i, /\bkaren\b/i, /\btessa\b/i, /\bzira\b/i, /\bjenny\b/i, /\bvictoria\b/i, /\bfemale\b/i],
  },
  old: {
    pitch: 0.85, rate: 0.82,
    prefer: [/\bdaniel\b/i, /\barthur\b/i, /\bmoira\b/i, /\boliver\b/i, /\bgeorge\b/i, /\bUK\b/, /\bBritish\b/i],
  },
  robotic: {
    pitch: 0.4, rate: 1.0,
    prefer: [/\bzarvox\b/i, /\btrinoids\b/i, /\brobot/i, /\bfred\b/i, /\bralph\b/i],
  },
};
const DEFAULT_SETTINGS = { pitch: 1, rate: 1, prefer: [] };

export function voiceSettings(hint) {
  return VOICE_HINTS[String(hint || "").toLowerCase()] ?? DEFAULT_SETTINGS;
}

const isEnglish = (v) => /^en([-_]|$)/i.test(v?.lang || "");

/** Pure: choose a SpeechSynthesisVoice for a hint. English first; null if there are no voices. */
export function pickVoice(voices, hint) {
  const all = Array.from(voices || []);
  if (!all.length) return null;
  const english = all.filter(isEnglish);
  const pool = english.length ? english : all;
  for (const re of voiceSettings(hint).prefer) {
    const hit = pool.find((v) => re.test(v.name || "") || re.test(v.voiceURI || ""));
    if (hit) return hit;
  }
  return (
    pool.find((v) => v.default) ||
    pool.find((v) => /^en[-_]GB/i.test(v.lang)) ||
    pool.find((v) => v.localService) ||
    pool[0]
  );
}

export function createTts(opts = {}) {
  const synth = opts.synth !== undefined ? opts.synth : globalThis.speechSynthesis;
  const Utterance = opts.Utterance || globalThis.SpeechSynthesisUtterance;
  const setTimer = opts.setTimeout || globalThis.setTimeout.bind(globalThis);
  const clearTimer = opts.clearTimeout || globalThis.clearTimeout.bind(globalThis);

  // ---- HOOK: server TTS (e.g. Gemini TTS) — NOT enabled by default -------------------------------
  // Pass `createTts({ serverTts: async ({ id, text, voice }) => audio })` where `audio` is a Blob, an
  // ArrayBuffer or a URL string. It is played with an <audio> element; if it throws or will not play,
  // the line falls back to speechSynthesis.
  const serverTts = opts.serverTts || null;
  const AudioCtor = opts.Audio || globalThis.Audio;
  // -----------------------------------------------------------------------------------------------

  let pending = null; // { finish } for the line being spoken

  // Voices load asynchronously in Chrome: ask once now so they are ready, and re-read the list per line.
  try { synth?.getVoices?.(); } catch { /* ignore */ }

  function finishPending() {
    const p = pending;
    pending = null;
    p?.finish();
  }

  function speakBrowser(text, hint) {
    if (!synth || !Utterance) {
      console.warn("[tts] speechSynthesis unavailable; skipping:", text);
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      const u = new Utterance(text);
      const settings = voiceSettings(hint);
      const voice = pickVoice(synth.getVoices?.() || [], hint);
      if (voice) u.voice = voice;
      u.lang = voice?.lang || "en-GB";
      u.pitch = settings.pitch;
      u.rate = settings.rate;
      u.volume = 1;
      let done = false;
      let timer = null;
      const finish = () => {
        if (done) return;
        done = true;
        if (timer !== null) clearTimer(timer);
        if (pending?.finish === finish) pending = null;
        resolve();
      };
      u.onend = finish;
      u.onerror = finish;
      timer = setTimer(finish, (text.length / CHARS_PER_S + SAFETY_PAD_S) * 1000);
      pending = { finish };
      synth.speak(u);
    });
  }

  async function speakServer(line) {
    const audio = await serverTts(line);
    if (!audio) throw new Error("server TTS returned nothing");
    const url = typeof audio === "string"
      ? audio
      : URL.createObjectURL(audio instanceof Blob ? audio : new Blob([audio]));
    const el = new AudioCtor(url);
    await new Promise((resolve, reject) => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        if (pending?.finish === finish) pending = null;
        resolve();
      };
      el.onended = finish;
      el.onerror = finish;
      pending = { finish: () => { el.pause?.(); finish(); } };
      Promise.resolve(el.play()).catch((e) => { done = true; pending = null; reject(e); });
    });
  }

  async function speak({ id, text, voice } = {}) {
    const line = String(text || "").trim();
    if (!line) return;
    if (pending) cancel(); // never talk over ourselves
    if (serverTts) {
      try {
        await speakServer({ id, text: line, voice });
        return;
      } catch (e) {
        console.warn("[tts] server TTS failed, using speechSynthesis:", e?.message || e);
      }
    }
    await speakBrowser(line, voice);
  }

  function cancel() {
    try {
      synth?.cancel?.();
    } catch (e) {
      console.warn("[tts] cancel failed", e);
    }
    finishPending();
  }

  return { speak, cancel };
}
