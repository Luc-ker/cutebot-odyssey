// Sound effects synthesised with the Web Audio API (T81, whitepaper §7.1, §7.8, §7.11; contract C9).
// No audio files: every sound is built from oscillators and filtered noise, so nothing needs a licence.
//
//   const sfx = createSfx();
//   await sfx.unlock();          // from a click: browsers only start audio after a user gesture
//   sfx.play("warning");         // returns the name actually played ("chime" for unknown names)
//   sfx.duck(true);              // -50 % while the narrator speaks
//
// Names: warning, chime, landing, whoosh, bell, horn_<setting> for the 8 fallback settings, and every
// `sfx` in shared/roles.json. Anything else plays the fallback, `chime`.

export const SETTINGS = ["ocean", "wasteland", "snow", "kingdom", "neon_city", "jungle", "royal_court", "space_station"];
export const FALLBACK = "chime";
const MASTER_VOLUME = 0.8;
const DUCK_LEVEL = 0.5;
const SILENT = 0.0001; // exponential ramps can't reach 0

// ---- primitives --------------------------------------------------------------------------------

function makeKit(ctx, out, getNoise) {
  /** One oscillator note with an attack/decay envelope, optional glide, filter and vibrato. */
  function tone({ f, f2, type = "sine", t, dur, vol = 0.3, attack = 0.005, lp, vib, vibDepth = 8 }) {
    const osc = ctx.createOscillator();
    const env = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(f, t);
    if (f2) osc.frequency.exponentialRampToValueAtTime(f2, t + dur);
    const a = Math.min(attack, dur / 2);
    env.gain.setValueAtTime(SILENT, t);
    env.gain.exponentialRampToValueAtTime(vol, t + a);
    env.gain.exponentialRampToValueAtTime(SILENT, t + dur);
    let head = osc;
    if (lp) {
      const filt = ctx.createBiquadFilter();
      filt.type = "lowpass";
      filt.frequency.setValueAtTime(lp, t);
      head.connect(filt);
      head = filt;
    }
    head.connect(env);
    env.connect(out);
    if (vib) {
      const lfo = ctx.createOscillator();
      const depth = ctx.createGain();
      lfo.frequency.setValueAtTime(vib, t);
      depth.gain.setValueAtTime(vibDepth, t);
      lfo.connect(depth);
      depth.connect(osc.frequency);
      lfo.start(t);
      lfo.stop(t + dur + 0.05);
    }
    osc.start(t);
    osc.stop(t + dur + 0.05);
  }

  /** A burst of white noise through a filter, optionally sweeping the filter frequency. */
  function noise({ t, dur, vol = 0.3, filter = "lowpass", f = 1000, f2, q = 1, attack = 0.005 }) {
    const src = ctx.createBufferSource();
    src.buffer = getNoise();
    src.loop = true;
    const filt = ctx.createBiquadFilter();
    filt.type = filter;
    filt.Q.setValueAtTime(q, t);
    filt.frequency.setValueAtTime(f, t);
    if (f2) filt.frequency.exponentialRampToValueAtTime(f2, t + dur);
    const env = ctx.createGain();
    const a = Math.min(attack, dur / 2);
    env.gain.setValueAtTime(SILENT, t);
    env.gain.exponentialRampToValueAtTime(vol, t + a);
    env.gain.exponentialRampToValueAtTime(SILENT, t + dur);
    src.connect(filt);
    filt.connect(env);
    env.connect(out);
    src.start(t);
    src.stop(t + dur + 0.05);
  }

  /** Inharmonic partials with long decays: bells and gongs. */
  function bell({ f, t, dur = 2, vol = 0.3, ratios = [1, 2.76, 5.4, 8.93] }) {
    ratios.forEach((r, i) => tone({ f: f * r, t, dur: dur / (1 + i * 0.5), vol: vol / (i + 1), attack: 0.002 }));
  }

  return { tone, noise, bell };
}

// ---- recipes: (kit, t) => void ------------------------------------------------------------------

const brass = (k, t, notes, { type = "sawtooth", lp = 1800, vol = 0.22 } = {}) => {
  let at = t;
  for (const [f, dur] of notes) {
    k.tone({ f, type, t: at, dur, vol, attack: 0.03, lp });
    k.tone({ f: f * 1.005, type, t: at, dur, vol: vol * 0.5, attack: 0.03, lp }); // slight chorus
    at += dur * 0.92;
  }
};

export const RECIPES = {
  // --- core -------------------------------------------------------------------------------------
  warning: (k, t) => { for (let i = 0; i < 4; i++) k.tone({ f: i % 2 ? 660 : 880, type: "square", t: t + i * 0.18, dur: 0.16, vol: 0.18, lp: 3000 }); },
  chime: (k, t) => { [1047, 1319, 1568].forEach((f, i) => k.tone({ f, t: t + i * 0.09, dur: 1.2, vol: 0.22, attack: 0.003 })); },
  landing: (k, t) => { k.tone({ f: 140, f2: 40, t, dur: 0.35, vol: 0.7 }); k.noise({ t, dur: 0.25, vol: 0.35, f: 400 }); },
  whoosh: (k, t) => { k.noise({ t, dur: 0.55, vol: 0.45, filter: "bandpass", f: 300, f2: 3000, q: 1.5, attack: 0.25 }); },
  bell: (k, t) => { k.bell({ f: 660, t, dur: 2.2, vol: 0.3 }); },

  // --- horns, one per fallback setting (T84 picks the name) ---------------------------------------
  horn_kingdom: (k, t) => brass(k, t, [[392, 0.22], [523, 0.7]]),
  horn_ocean: (k, t) => { k.bell({ f: 880, t, dur: 1.4, vol: 0.3 }); k.bell({ f: 880, t: t + 0.35, dur: 1.6, vol: 0.3 }); }, // ship's bell: ding-ding
  horn_wasteland: (k, t) => {
    k.tone({ f: 73, f2: 62, type: "sawtooth", t, dur: 1.3, vol: 0.35, attack: 0.08, lp: 700, vib: 7, vibDepth: 3 });
    k.tone({ f: 74.5, f2: 63, type: "sawtooth", t, dur: 1.3, vol: 0.25, attack: 0.08, lp: 700 });
    k.noise({ t, dur: 1.2, vol: 0.2, f: 220, attack: 0.1 });
  },
  horn_snow: (k, t) => { k.tone({ f: 196, f2: 220, type: "triangle", t, dur: 1.5, vol: 0.35, attack: 0.18, vib: 5, vibDepth: 3 }); }, // alphorn
  horn_neon_city: (k, t) => {
    for (const at of [t, t + 0.32]) {
      k.tone({ f: 440, type: "square", t: at, dur: 0.24, vol: 0.14, lp: 2500 });
      k.tone({ f: 554, type: "square", t: at, dur: 0.24, vol: 0.14, lp: 2500 });
    }
  },
  horn_jungle: (k, t) => { // conch shell
    k.tone({ f: 311, f2: 330, type: "triangle", t, dur: 1.3, vol: 0.35, attack: 0.12, vib: 5, vibDepth: 4 });
    k.tone({ f: 622, f2: 660, t, dur: 1.2, vol: 0.08, attack: 0.15 });
  },
  horn_royal_court: (k, t) => brass(k, t, [[523, 0.13], [659, 0.13], [784, 0.13], [1047, 0.55]], { lp: 3200, vol: 0.18 }),
  horn_space_station: (k, t) => {
    k.tone({ f: 200, f2: 900, t, dur: 0.7, vol: 0.25, vib: 12, vibDepth: 20 });
    k.tone({ f: 100, type: "square", t, dur: 0.7, vol: 0.12, lp: 600 });
  },

  // --- role sounds (shared/roles.json `sfx`) -------------------------------------------------------
  fanfare: (k, t) => brass(k, t, [[392, 0.14], [494, 0.14], [587, 0.14], [784, 0.6]], { lp: 3000, vol: 0.18 }),
  horn: (k, t) => brass(k, t, [[294, 0.25], [392, 0.8]], { lp: 1400 }),
  foghorn: (k, t) => { k.tone({ f: 82, type: "sawtooth", t, dur: 1.7, vol: 0.4, attack: 0.25, lp: 500 }); k.tone({ f: 82.6, type: "sawtooth", t, dur: 1.7, vol: 0.3, attack: 0.25, lp: 500 }); },
  drums: (k, t) => { [0, 0.2, 0.4, 0.5].forEach((d, i) => { k.tone({ f: i === 3 ? 140 : 110, f2: 50, t: t + d, dur: 0.22, vol: 0.6 }); k.noise({ t: t + d, dur: 0.06, vol: 0.2, f: 800 }); }); },
  gong: (k, t) => { k.bell({ f: 110, t, dur: 3.5, vol: 0.45, ratios: [1, 1.48, 2.1, 2.9, 4.2] }); k.noise({ t, dur: 0.15, vol: 0.15, f: 600 }); },
  hum: (k, t) => { k.tone({ f: 110, type: "sawtooth", t, dur: 1.3, vol: 0.2, attack: 0.2, lp: 400 }); k.tone({ f: 111, type: "sawtooth", t, dur: 1.3, vol: 0.2, attack: 0.2, lp: 400 }); },
  chatter: (k, t) => { for (let i = 0; i < 7; i++) k.noise({ t: t + i * 0.09 + (i % 3) * 0.03, dur: 0.07, vol: 0.18, filter: "bandpass", f: 900 + ((i * 373) % 1100), q: 6 }); },
  waves: (k, t) => { k.noise({ t, dur: 2.2, vol: 0.4, f: 900, f2: 250, attack: 0.9 }); },
  crackle: (k, t) => { for (let i = 0; i < 14; i++) k.noise({ t: t + ((i * 137) % 100) / 100, dur: 0.02, vol: 0.3, filter: "highpass", f: 2500 }); },
  creak: (k, t) => { k.tone({ f: 180, f2: 140, type: "sawtooth", t, dur: 0.7, vol: 0.18, attack: 0.05, lp: 900, vib: 18, vibDepth: 12 }); },
  splash: (k, t) => { k.noise({ t, dur: 0.4, vol: 0.4, filter: "highpass", f: 1500, f2: 600 }); k.noise({ t, dur: 0.2, vol: 0.3, f: 800 }); },
  birds: (k, t) => { [0, 0.12, 0.42, 0.52].forEach((d) => k.tone({ f: 2500, f2: 3600, t: t + d, dur: 0.08, vol: 0.12 })); },
  wind: (k, t) => { k.noise({ t, dur: 2.0, vol: 0.35, filter: "bandpass", f: 400, f2: 750, q: 0.8, attack: 0.7 }); },
  rumble: (k, t) => { k.noise({ t, dur: 1.6, vol: 0.7, f: 120, attack: 0.25 }); k.tone({ f: 45, t, dur: 1.6, vol: 0.35, attack: 0.25 }); },
  crack: (k, t) => { k.noise({ t, dur: 0.05, vol: 0.7, filter: "highpass", f: 2000 }); k.noise({ t: t + 0.03, dur: 0.35, vol: 0.3, filter: "bandpass", f: 900 }); },
  stream: (k, t) => { k.noise({ t, dur: 1.6, vol: 0.22, filter: "bandpass", f: 1200, q: 3, attack: 0.3 }); [0.2, 0.55, 0.9, 1.2].forEach((d, i) => k.tone({ f: 1800 + i * 150, f2: 2400, t: t + d, dur: 0.06, vol: 0.06 })); },
  hooves: (k, t) => { [0, 0.18, 0.3, 0.48].forEach((d) => { k.tone({ f: 600, f2: 300, t: t + d, dur: 0.05, vol: 0.3 }); k.noise({ t: t + d, dur: 0.04, vol: 0.2, filter: "bandpass", f: 1200 }); }); },
  coins: (k, t) => { [2093, 2637, 2349, 2794, 3136].forEach((f, i) => k.tone({ f, type: "triangle", t: t + i * 0.07, dur: 0.18, vol: 0.12, attack: 0.002 })); },
  shimmer: (k, t) => { [1568, 1760, 2093, 2349, 2637, 3136].forEach((f, i) => k.tone({ f, t: t + i * 0.05, dur: 0.7, vol: 0.08 })); },
  roar: (k, t) => { k.tone({ f: 150, f2: 80, type: "sawtooth", t, dur: 1.0, vol: 0.4, attack: 0.08, lp: 900, vib: 30, vibDepth: 15 }); k.noise({ t, dur: 1.0, vol: 0.35, f: 700, attack: 0.08 }); },
  hiss: (k, t) => { k.noise({ t, dur: 0.9, vol: 0.3, filter: "highpass", f: 4000, attack: 0.12 }); },
  growl: (k, t) => { k.tone({ f: 90, f2: 75, type: "sawtooth", t, dur: 0.85, vol: 0.4, attack: 0.06, lp: 500, vib: 25, vibDepth: 15 }); },
  howl: (k, t) => { k.tone({ f: 400, f2: 700, type: "triangle", t, dur: 0.6, vol: 0.25, attack: 0.25, vib: 6, vibDepth: 6 }); k.tone({ f: 700, f2: 480, type: "triangle", t: t + 0.58, dur: 1.0, vol: 0.25, attack: 0.02, vib: 6, vibDepth: 6 }); },
  beep: (k, t) => { [0, 0.18].forEach((d) => k.tone({ f: 1000, type: "square", t: t + d, dur: 0.1, vol: 0.12, lp: 4000 })); },
  boom: (k, t) => { k.tone({ f: 80, f2: 30, t, dur: 1.1, vol: 0.9 }); k.noise({ t, dur: 0.6, vol: 0.5, f: 300 }); },
  synth: (k, t) => { [220, 277, 330, 440, 330, 277].forEach((f, i) => k.tone({ f, type: "sawtooth", t: t + i * 0.1, dur: 0.12, vol: 0.12, lp: 2000 })); },
  buzz: (k, t) => { k.tone({ f: 220, type: "sawtooth", t, dur: 0.9, vol: 0.15, lp: 1500, vib: 40, vibDepth: 12 }); k.tone({ f: 223, type: "sawtooth", t, dur: 0.9, vol: 0.12, lp: 1500 }); },
  drip: (k, t) => { k.tone({ f: 900, f2: 1700, t, dur: 0.09, vol: 0.25 }); k.tone({ f: 1000, f2: 1900, t: t + 0.55, dur: 0.09, vol: 0.2 }); },
};

export function soundNames() {
  return Object.keys(RECIPES);
}

export function resolveName(name) {
  return Object.hasOwn(RECIPES, name) ? name : FALLBACK;
}

// ---- the player ---------------------------------------------------------------------------------

export function createSfx(opts = {}) {
  const AudioCtor = opts.AudioContext || globalThis.AudioContext || globalThis.webkitAudioContext;
  let ctx = opts.ctx || null;
  let master = null;
  let ducker = null;
  let noiseBuf = null;
  let kit = null;

  function ensure() {
    if (ctx && kit) return true;
    if (!ctx) {
      if (!AudioCtor) return false;
      ctx = new AudioCtor();
    }
    master = ctx.createGain();
    master.gain.setValueAtTime(MASTER_VOLUME, ctx.currentTime);
    ducker = ctx.createGain();
    ducker.gain.setValueAtTime(1, ctx.currentTime);
    master.connect(ducker);
    ducker.connect(ctx.destination);
    kit = makeKit(ctx, master, getNoise);
    return true;
  }

  function getNoise() {
    if (!noiseBuf) {
      const len = Math.floor(ctx.sampleRate || 44100);
      noiseBuf = ctx.createBuffer(1, len, ctx.sampleRate || 44100);
      const data = noiseBuf.getChannelData(0);
      for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
    }
    return noiseBuf;
  }

  /** Create / resume the AudioContext. Call from a click handler. */
  async function unlock() {
    if (!ensure()) return false;
    if (ctx.state === "suspended" && ctx.resume) await ctx.resume();
    return true;
  }

  /** Play a named sound; unknown names play the fallback. Returns the name played, or null. */
  function play(name) {
    const key = resolveName(name);
    try {
      if (!ensure()) return null;
      RECIPES[key](kit, ctx.currentTime + 0.01);
      return key;
    } catch (e) {
      console.warn(`[sfx] could not play ${name}:`, e?.message || e);
      return null;
    }
  }

  /** Lower effects by 50 % while the narrator talks. */
  function duck(on) {
    if (!ensure()) return;
    ducker.gain.setTargetAtTime(on ? DUCK_LEVEL : 1, ctx.currentTime, 0.06);
  }

  return { play, duck, unlock, names: soundNames, get context() { return ctx; } };
}
