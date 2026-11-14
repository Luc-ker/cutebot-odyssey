// Shared beat envelope for the overhead map (T93, whitepaper §7.9).
//
//   beatEnvelope(now, lastBeatT, tempoBpm, energy, opts) -> 0..1
//
// `now` and `lastBeatT` are seconds on the same clock (the map store stamps beats with its own clock on
// arrival, so sender clock skew doesn't matter). The value jumps to its peak on a beat (fast attack),
// falls to 0 over 40 % of the beat period, and is scaled by energy: full energy peaks at 1, quiet music
// at 0.3. It is 0 when `opts.silent` is true.
//
// Anticipation (on by default): between real beats the envelope keeps firing on the predicted grid
// (lastBeatT + k·period) for up to MAX_PREDICTED beats, starting the attack slightly early. This hides the
// network jitter of `audio.beat` messages and keeps the map pulsing smoothly if one message is late.

export const DECAY_FRACTION = 0.4;  // of the beat period
export const ATTACK_S = 0.03;       // rise time before a (predicted) beat
export const MAX_PREDICTED = 4;     // predicted beats after the last real one
export const MIN_SCALE = 0.3;       // envelope peak at energy 0

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export function periodFor(tempoBpm) {
  const bpm = Number.isFinite(tempoBpm) && tempoBpm > 0 ? clamp(tempoBpm, 40, 240) : 120;
  return 60 / bpm;
}

export function beatEnvelope(now, lastBeatT, tempoBpm, energy = 1, opts = {}) {
  if (opts.silent) return 0;
  if (!Number.isFinite(now) || !Number.isFinite(lastBeatT)) return 0;
  const period = periodFor(tempoBpm);
  const attack = Math.min(ATTACK_S, period * 0.1);
  let dt = now - lastBeatT;
  if (dt < -attack) return 0;

  const anticipate = opts.anticipate ?? true;
  if (anticipate && dt > period * DECAY_FRACTION) {
    if (dt > period * (MAX_PREDICTED + 0.5)) return 0; // the beat has stopped
    // Time relative to the nearest predicted beat, with the attack window before it counted as "after".
    dt = ((dt + attack) % period) - attack;
  }

  const e = Number.isFinite(energy) ? clamp(energy, 0, 1) : 1;
  const scale = MIN_SCALE + (1 - MIN_SCALE) * e;

  let shape;
  if (dt < 0) {
    shape = (dt + attack) / attack; // rising edge just before the beat
  } else {
    const x = dt / (period * DECAY_FRACTION);
    shape = x >= 1 ? 0 : (1 - x) * (1 - x);
  }
  return clamp(shape * scale, 0, 1);
}

/** Convenience for the map: the envelope from a store state (see store.js) at time `now`. */
export function beatFromState(state, now) {
  const beat = state?.["audio.beat"];
  const feats = state?.["audio.features"];
  return beatEnvelope(now, state?.lastBeatT, beat?.tempo_bpm, feats?.energy ?? beat?.strength ?? 1, {
    silent: Boolean(feats?.silent),
  });
}
