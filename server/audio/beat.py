"""Beat and tempo tracker (T65, whitepaper §7.6, §7.9, §10).

Publishes ``audio.beat {tempo_bpm, strength}`` (C3) on each beat, locally, with no network.

How it works (numpy only, causal):

1. **Onset strength.** Every ~10 ms, spectral flux of the log-compressed magnitude spectrum (how much
   new energy appeared). An onset is a local peak of the flux above an adaptive threshold.
2. **Tempo.** Every 0.5 s, autocorrelate the last 8 s of flux. Tempo is the lag (60-200 bpm) with the
   best score, ``ac[L] + 0.5·ac[2L]``, weighted by a prior centred on 120 bpm. Parabolic interpolation
   gives a fractional lag, and new estimates are smoothed so the tempo doesn't jitter.
3. **Beats.**
   - Before a tempo is known, every strong onset is a beat (at most 4 per second).
   - Once the tempo is known, a phase-locked grid takes over. A beat fires at the *predicted* time, or
     at an onset that arrives just before it. Onsets near a beat nudge the grid's phase.
   - Firing on the prediction instead of after detection keeps audio-to-publish latency to about one
     audio block (~23 ms).
   - The grid stops after 3 s without any onset and re-anchors on the next one.
4. **Silence.** No beats while the silence gate (T67) says silent, or while the last 0.5 s is below the
   gate's threshold (so beats stop within half a second of the music stopping). When the gate closes, the tempo is
   forgotten: whatever plays next is probably a different song.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

import numpy as np

from server.audio.silence import SilenceGate

HOP_S = 0.01
ENV_S = 8.0
TEMPO_EVERY_S = 0.5
MIN_TEMPO_HISTORY_S = 2.5
BPM_MIN, BPM_MAX = 60.0, 200.0
PRIOR_BPM, PRIOR_OCTAVES = 120.0, 0.9
MIN_ONSET_GAP_S = 0.25      # onset mode: at most 4 beats per second
PHASE_GAIN = 0.4            # how hard an onset pulls the grid
TOL_FRAC = 0.2              # onset counts as "the beat" within ±20 % of a period
GRID_TIMEOUT_S = 3.0
STRENGTH_PEAK_TAU_S = 10.0
GATE_WINDOW_S = 0.5         # the gate hears the RMS of the last 0.5 s, so gaps between hits aren't "silence"


def estimate_tempo(env: np.ndarray, fps: float) -> float | None:
    """Tempo in bpm from an onset-strength envelope, or None if there's no rhythm."""
    if len(env) < fps * MIN_TEMPO_HISTORY_S:
        return None
    e = env - env.mean()
    if not np.any(e):
        return None
    n = len(e)
    spec = np.fft.rfft(e, 2 * n)
    ac = np.fft.irfft(spec * np.conj(spec))[:n]
    if ac[0] <= 0:
        return None
    ac = ac / ac[0]
    lo = max(2, int(math.floor(60.0 * fps / BPM_MAX)))
    hi = min(n - 2, int(math.ceil(60.0 * fps / BPM_MIN)))
    if hi <= lo:
        return None
    lags = np.arange(lo, hi + 1)
    second = np.where(2 * lags < n, ac[np.minimum(2 * lags, n - 1)], 0.0)
    score = ac[lags] + 0.5 * second
    bpm = 60.0 * fps / lags
    prior = np.exp(-0.5 * (np.log2(bpm / PRIOR_BPM) / PRIOR_OCTAVES) ** 2)
    i = int(np.argmax(score * prior))
    if score[i] <= 0.05:
        return None
    L = float(lags[i])
    if 0 < i < len(lags) - 1:  # parabolic refinement on the raw autocorrelation
        a, b, c = ac[lags[i] - 1], ac[lags[i]], ac[lags[i] + 1]
        denom = a - 2 * b + c
        if denom < 0:
            L += 0.5 * (a - c) / denom
    return 60.0 * fps / L


class BeatTracker:
    def __init__(self, rate: int, gate: SilenceGate | None = None):
        self.rate = rate
        self.hop = max(1, int(round(rate * HOP_S)))
        self.fps = rate / self.hop
        self.n_fft = 1 << int(math.ceil(math.log2(max(256, rate * 0.023))))
        self.window = np.hanning(self.n_fft).astype(np.float32)
        self.gate = gate or SilenceGate()
        self.reset()

    def reset(self) -> None:
        self._pending = np.zeros(0, np.float32)
        self._gate_power: list[tuple[float, float]] = []  # (block energy, n samples) over GATE_WINDOW_S
        self._buf = np.zeros(self.n_fft, np.float32)
        self._prev_spec: np.ndarray | None = None
        self._env: list[float] = []
        self._flux = [0.0, 0.0, 0.0]  # last three flux values (for peak picking)
        self._frames = 0
        self._next_tempo_at = 0
        self._peak = 1e-6
        self.period: float | None = None  # seconds per beat
        self._candidate: float | None = None
        self.next_beat: float | None = None
        self.last_beat: float | None = None
        self._last_onset: float | None = None
        self._last_beat_t_was_prediction = False
        self._strength_ema = 0.5
        self._iois: list[float] = []
        self.silent = True
        self._quiet = True
        self.gate.reset()

    @property
    def tempo_bpm(self) -> float:
        if self.period:
            return 60.0 / self.period
        if len(self._iois) >= 2:
            return 60.0 / float(np.median(self._iois[-8:]))
        return 0.0

    # ---- public --------------------------------------------------------------------------------
    def process(self, samples: np.ndarray, ts: float, silent: bool | None = None) -> list[dict]:
        """Feed a block; ``ts`` is the time of its last sample. Returns the beats it contains:
        ``[{"ts", "tempo_bpm", "strength"}]``. ``silent`` overrides the built-in silence gate."""
        samples = np.asarray(samples, np.float32)
        level = self._window_rms(samples)
        if silent is None:
            silent = self.gate.update(level, ts)
        if silent and not self.silent:
            self._forget_song()  # music stopped: whatever comes next is probably a new song
        self.silent = silent
        # Quiet over the last 0.5 s (music just stopped, before the gate's 1.5 s): stop ticking the grid.
        self._quiet = level < self.gate.threshold

        x = np.concatenate([self._pending, samples])
        n_hops = len(x) // self.hop
        beats: list[dict] = []
        for i in range(n_hops):
            frame = x[i * self.hop:(i + 1) * self.hop]
            t = ts - (len(x) - (i + 1) * self.hop) / self.rate
            beats += self._frame(frame, t)
        self._pending = x[n_hops * self.hop:]
        return beats

    # ---- internals -----------------------------------------------------------------------------
    def _window_rms(self, samples: np.ndarray) -> float:
        if len(samples):
            self._gate_power.append((float(np.sum(samples.astype(np.float64) ** 2)), len(samples)))
        keep, total = [], 0
        for e, n in reversed(self._gate_power):
            if total >= GATE_WINDOW_S * self.rate:
                break
            keep.append((e, n))
            total += n
        self._gate_power = keep[::-1]
        return math.sqrt(sum(e for e, _ in keep) / total) if total else 0.0

    def _frame(self, frame: np.ndarray, t: float) -> list[dict]:
        self._buf = np.concatenate([self._buf[len(frame):], frame])
        spec = np.log1p(100.0 * np.abs(np.fft.rfft(self._buf * self.window)))
        flux = 0.0 if self._prev_spec is None else float(np.maximum(spec - self._prev_spec, 0).mean())
        self._prev_spec = spec
        self._env.append(flux)
        max_env = int(ENV_S * self.fps)
        if len(self._env) > max_env:
            del self._env[: len(self._env) - max_env]
        self._flux = self._flux[1:] + [flux]
        self._peak = max(flux, self._peak * math.exp(-HOP_S / STRENGTH_PEAK_TAU_S))
        self._frames += 1

        if self._frames >= self._next_tempo_at:
            self._next_tempo_at = self._frames + int(TEMPO_EVERY_S * self.fps)
            self._update_tempo(t)

        out: list[dict] = []
        if self.silent or self._quiet:
            return out
        onset = self._detect_onset()
        if onset is not None:
            out += self._on_onset(t - 1.0 / self.fps, onset)  # the peak was the previous frame
        if self.period and self.next_beat is not None:
            if self._last_onset is None or t - self._last_onset > GRID_TIMEOUT_S:
                self.next_beat = None  # no rhythm any more: back to onset mode
            elif t >= self.next_beat:
                p = self.next_beat
                out.append(self._emit(p, self._strength_ema * 0.8, prediction=True))
                self.next_beat = p + self.period
        return out

    def _forget_song(self) -> None:
        self._env.clear()
        self.period = None
        self._candidate = None
        self.next_beat = None
        self.last_beat = None
        self._last_onset = None
        self._iois = []

    def _detect_onset(self) -> float | None:
        a, b, c = self._flux
        if not (b > a and b >= c):
            return None
        recent = np.asarray(self._env[-int(1.5 * self.fps):-1] or [0.0])
        threshold = recent.mean() + 1.5 * recent.std()
        if b <= max(threshold, 0.02 * self._peak, 1e-4):
            return None
        return min(1.0, b / self._peak)

    def _on_onset(self, t: float, strength: float) -> list[dict]:
        self._last_onset = t
        self._strength_ema = 0.8 * self._strength_ema + 0.2 * strength
        if not self.period:
            if self.last_beat is None or t - self.last_beat >= MIN_ONSET_GAP_S:
                return [self._emit(t, strength, prediction=False)]
            return []
        if self.next_beat is None:  # (re)anchor the grid on this onset
            self.next_beat = t + self.period
            return [self._emit(t, strength, prediction=False)]
        tol = TOL_FRAC * self.period
        p = self.next_beat
        if p - tol <= t < p:  # the beat arrived a little early: fire it now
            self.next_beat = p + self.period + PHASE_GAIN * (t - p)
            return [self._emit(t, strength, prediction=False)]
        if self.last_beat is not None and self._last_beat_t_was_prediction and 0 <= t - self.last_beat <= tol:
            # the predicted beat already fired and the real onset came just after: pull the grid later
            self.next_beat += PHASE_GAIN * (t - self.last_beat)
            self._last_beat_t_was_prediction = False
        return []

    def _emit(self, t: float, strength: float, prediction: bool) -> dict:
        if self.last_beat is not None and t > self.last_beat:
            ioi = t - self.last_beat
            if 60.0 / BPM_MAX * 0.9 <= ioi <= 60.0 / BPM_MIN * 1.1:
                self._iois = (self._iois + [ioi])[-16:]
        self.last_beat = t
        self._last_beat_t_was_prediction = prediction
        return {"ts": t, "tempo_bpm": round(self.tempo_bpm, 1), "strength": round(float(min(1.0, max(0.0, strength))), 3)}

    def _update_tempo(self, t: float) -> None:
        bpm = estimate_tempo(np.asarray(self._env), self.fps)
        if bpm is None:
            return
        period = 60.0 / bpm
        if self.period is None:
            self.period = period
            if self.last_beat is not None and self.next_beat is None and self._last_onset is not None:
                nb = self.last_beat + period
                while nb < t:
                    nb += period
                self.next_beat = nb
        elif abs(period / self.period - 1) < 0.08:
            self.period = 0.8 * self.period + 0.2 * period
            self._candidate = None
        elif self._candidate and abs(period / self._candidate - 1) < 0.08:
            self.period = period  # the new tempo held for two estimates in a row: switch
            self._candidate = None
        else:
            self._candidate = period


async def run(hub: Any, config: dict | None = None, audio=None) -> None:
    """Brain entrypoint (C7). Pass the shared ``AudioInput`` as ``audio``; one is made if absent."""
    if audio is None:
        from server.audio.capture import AudioInput
        audio = AudioInput(config or {}).start()
    loop = asyncio.get_running_loop()
    tracker = BeatTracker(audio.rate)

    def on_block(samples, ts):  # audio thread: publish straight away, no batching
        for b in tracker.process(samples, ts):
            data = {"tempo_bpm": b["tempo_bpm"], "strength": b["strength"]}
            asyncio.run_coroutine_threadsafe(hub.pub("audio.beat", data), loop)

    async def on_reset(_env):
        tracker.reset()

    hub.sub("system.reset", on_reset)
    audio.on_block(on_block)
    await asyncio.Event().wait()
