"""Music change detection (T69, whitepaper §7.6, §7.7).

C7: ``ChangeDetector().update(samples, ts) -> bool``: True once per detected song change, so the world
loop (T74) can ask Gemini early instead of waiting for the next timed check.

Every 100 ms it computes a frame of features: chroma (harmony), loudness in dB, brightness (spectral
centroid) and onset flux (rhythmic activity, a cheap stand-in for tempo over a 3 s window). It then
compares the mean of the **last 3 s** against the **previous up-to-8 s**:

    score = 0.5·key + 0.2·loudness + 0.15·brightness + 0.15·rhythm   (each part 0-1)

where "key" compares which major/minor keys fit each window's chroma (see ``key_distance``).
A change fires when the score stays above 0.45 for 0.3 s, at most once per 6 s cooldown. After a change
the history restarts, so the old song can't trigger again.

**Silence → music counts as a change**, but only after silence was actually heard (the silence gate
said silent). A detector that starts while music is already playing does not fire.
"""

from __future__ import annotations

import math
from collections import deque

import numpy as np

from server.audio.silence import SilenceGate

HOP_S = 0.1
RECENT_S = 3.0
PREVIOUS_S = 8.0
MIN_PREVIOUS_S = 4.0
COOLDOWN_S = 6.0
THRESHOLD = 0.45
HOLD_FRAMES = 3
GATE_WINDOW_FRAMES = 5      # gate hears the RMS of the last 0.5 s
WEIGHTS = (0.5, 0.2, 0.15, 0.15)
# Harmony is compared by *key*, not raw chroma: 3 s of a song covers only a chord or two, which looks
# very different from an 8 s average even within one song. Correlating each window's chroma with the
# 24 Krumhansl-Kessler key profiles gives a "which keys fit" vector that stays stable through a chord
# progression and moves when the key changes. Key-vector cosine distance runs 0-2; map KEY_LO-KEY_HI -> 0-1.
KEY_LO, KEY_HI = 0.6, 1.4
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_KEYS = np.array([np.roll(_MAJOR, k) for k in range(12)] + [np.roll(_MINOR, k) for k in range(12)])
_KEYS = _KEYS - _KEYS.mean(axis=1, keepdims=True)
_KEYS /= np.linalg.norm(_KEYS, axis=1, keepdims=True)


def key_vector(chroma: np.ndarray) -> np.ndarray:
    """Correlation of a 12-bin chroma with each of the 24 major/minor key profiles."""
    c = np.asarray(chroma, float) - np.mean(chroma)
    n = np.linalg.norm(c)
    return _KEYS @ (c / n) if n > 0 else np.zeros(24)


def key_distance(chroma_a: np.ndarray, chroma_b: np.ndarray) -> float:
    ka, kb = key_vector(chroma_a), key_vector(chroma_b)
    na, nb = np.linalg.norm(ka), np.linalg.norm(kb)
    return 1.0 - float(ka @ kb / (na * nb)) if na > 0 and nb > 0 else 0.0
LOUDNESS_SCALE_DB = 10.0
BRIGHTNESS_SCALE = 0.2
RHYTHM_SCALE = math.log(2.0)


class ChangeDetector:
    def __init__(self, rate: int = 44100):
        self.rate = rate
        self.hop = int(round(rate * HOP_S))
        self.n_fft = 1 << int(math.ceil(math.log2(rate * 0.093)))
        self.window = np.hanning(self.n_fft)
        freqs = np.fft.rfftfreq(self.n_fft, 1.0 / rate)
        band = (freqs >= 55) & (freqs <= 5000)
        self._band = band
        self._pc = (np.round(12 * np.log2(freqs[band] / 440.0)).astype(int) + 9) % 12
        self._freqs = freqs
        self.reset()

    def reset(self) -> None:
        self._pending = np.zeros(0, np.float32)
        self._buf = np.zeros(self.n_fft, np.float32)
        self._prev_mag: np.ndarray | None = None
        self._frames: deque = deque(maxlen=int((RECENT_S + PREVIOUS_S) / HOP_S))
        self._powers: deque = deque(maxlen=GATE_WINDOW_FRAMES)
        self.gate = SilenceGate(start_silent=False)
        self._heard_silence = False
        self._last_change = -math.inf
        self._above = 0
        self.last_score = 0.0

    def update(self, samples: np.ndarray, ts: float) -> bool:
        """Feed a block (``ts`` = time of its last sample). True if a change was detected in it."""
        x = np.concatenate([self._pending, np.asarray(samples, np.float32)])
        n = len(x) // self.hop
        changed = False
        for i in range(n):
            t = ts - (len(x) - (i + 1) * self.hop) / self.rate
            changed |= self._frame(x[i * self.hop:(i + 1) * self.hop], t)
        self._pending = x[n * self.hop:]
        return changed

    # ---- internals -----------------------------------------------------------------------------
    def _frame(self, frame: np.ndarray, t: float) -> bool:
        self._buf = np.concatenate([self._buf[len(frame):], frame])
        rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))
        self._powers.append(rms * rms)
        silent = self.gate.update(math.sqrt(sum(self._powers) / len(self._powers)), t)

        if silent:
            self._heard_silence = True
            self._frames.clear()
            self._prev_mag = None
            self._above = 0
            return False
        if self._heard_silence:  # music after real silence
            self._heard_silence = False
            return self._fire(t)

        if rms < self.gate.threshold:
            # A quiet frame (music stopping, a pause) says nothing about which song this is. Leave it out,
            # so a fade to silence can't look like a new song before the gate declares silence.
            self._above = 0
            return False

        mag = np.abs(np.fft.rfft(self._buf * self.window))
        power = mag[self._band] ** 2
        chroma = np.bincount(self._pc, weights=power, minlength=12)
        s = chroma.sum()
        chroma = chroma / s if s > 0 else chroma
        total = mag.sum()
        centroid = float(mag @ self._freqs / total) if total > 0 else 0.0
        bright = 0.0 if centroid <= 0 else min(1.0, max(0.0, math.log(max(centroid, 150) / 150) / math.log(8000 / 150)))
        log_mag = np.log1p(100 * mag)
        flux = 0.0 if self._prev_mag is None else float(np.maximum(log_mag - self._prev_mag, 0).mean())
        self._prev_mag = log_mag
        self._frames.append((chroma, 20 * math.log10(max(rms, 1e-9)), bright, flux))

        score = self._score()
        self.last_score = score
        self._above = self._above + 1 if score > THRESHOLD else 0
        if self._above >= HOLD_FRAMES:
            return self._fire(t)
        return False

    def _score(self) -> float:
        n_recent = int(RECENT_S / HOP_S)
        n_prev_min = int(MIN_PREVIOUS_S / HOP_S)
        if len(self._frames) < n_recent + n_prev_min:
            return 0.0
        frames = list(self._frames)
        recent, prev = frames[-n_recent:], frames[:-n_recent]

        def means(fs):
            return (np.mean([f[0] for f in fs], axis=0), np.mean([f[1] for f in fs]),
                    np.mean([f[2] for f in fs]), np.mean([f[3] for f in fs]))

        cr, lr, br, fr = means(recent)
        cp, lp, bp, fp = means(prev)
        d_key = key_distance(cr, cp)
        parts = (
            min(1.0, max(0.0, (d_key - KEY_LO) / (KEY_HI - KEY_LO))),
            min(1.0, abs(lr - lp) / LOUDNESS_SCALE_DB),
            min(1.0, abs(br - bp) / BRIGHTNESS_SCALE),
            min(1.0, abs(math.log((fr + 1e-4) / (fp + 1e-4))) / RHYTHM_SCALE),
        )
        return float(sum(w * p for w, p in zip(WEIGHTS, parts)))

    def _fire(self, t: float) -> bool:
        self._above = 0
        if t - self._last_change < COOLDOWN_S:
            return False
        self._last_change = t
        # Start a fresh history: keep only the last second, which is (mostly) the new song.
        keep = list(self._frames)[-int(1.0 / HOP_S):]
        self._frames.clear()
        self._frames.extend(keep)
        return True
