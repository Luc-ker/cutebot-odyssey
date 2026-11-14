"""Music signature (T70, whitepaper §7.12, §9).

A compact fingerprint of a song's feel, stored as a world's ``music_signature`` (C4), so a song that
comes back can restore its world (T54).

C7: ``signature(window, rate=44100) -> {tempo_bpm, energy, brightness, chroma[12]}``,
``distance(a, b) -> float`` in 0-1.

- ``tempo_bpm``: autocorrelation of a spectral-flux onset envelope (0 when there's no clear pulse).
- ``energy`` (0-1): overall loudness, -50 dBFS → 0 and -6 dBFS → 1. It depends on playback level, so it
  has a small weight in :func:`distance`.
- ``brightness`` (0-1): mean spectral centroid on a log scale, 150 Hz → 0 and 8 kHz → 1.
- ``chroma``: 12 pitch classes (C, C#, … B) of spectral power from 55 Hz to 5 kHz, L2-normalised.
  It captures key and harmony.

``distance`` mixes chroma cosine distance (0.4, saturating at 0.5), octave-aware tempo difference (0.3: 60 and 120 bpm
count as close), brightness (0.15) and energy (0.15).
"""

from __future__ import annotations

import math

import numpy as np

DEFAULT_RATE = 44100
CENTROID_LO, CENTROID_HI = 150.0, 8000.0
CHROMA_LO, CHROMA_HI = 55.0, 5000.0
BPM_MIN, BPM_MAX = 60.0, 200.0
WEIGHTS = {"chroma": 0.4, "tempo": 0.3, "brightness": 0.15, "energy": 0.15}
TEMPO_SCALE_OCTAVES = 0.2  # a tempo ratio of 2^0.2 (~15 %) or more counts as fully different
CHROMA_SCALE = 0.5         # chroma cosine distance of 0.5+ counts as fully different harmony
                           # (different keys still share notes, so raw cosine distances stay small)


def _frames(x: np.ndarray, n: int, hop: int) -> np.ndarray:
    if len(x) < n:
        x = np.pad(x, (0, n - len(x)))
    count = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(count)[:, None]
    return x[idx] * np.hanning(n)[None, :]


def _tempo(x: np.ndarray, rate: int) -> float:
    hop = max(1, rate // 100)
    n = 1 << int(math.ceil(math.log2(max(256, rate * 0.023))))
    if len(x) < rate * 2.5:
        return 0.0
    spec = np.log1p(100 * np.abs(np.fft.rfft(_frames(x, n, hop), axis=1)))
    env = np.maximum(np.diff(spec, axis=0), 0).mean(axis=1)
    fps = rate / hop
    e = env - env.mean()
    if not np.any(e):
        return 0.0
    m = len(e)
    s = np.fft.rfft(e, 2 * m)
    ac = np.fft.irfft(s * np.conj(s))[:m]
    if ac[0] <= 0:
        return 0.0
    ac /= ac[0]
    lags = np.arange(max(2, int(60 * fps / BPM_MAX)), min(m - 2, int(math.ceil(60 * fps / BPM_MIN))) + 1)
    if len(lags) == 0:
        return 0.0
    second = np.where(2 * lags < m, ac[np.minimum(2 * lags, m - 1)], 0.0)
    score = ac[lags] + 0.5 * second
    bpm = 60 * fps / lags
    prior = np.exp(-0.5 * (np.log2(bpm / 120.0) / 0.9) ** 2)
    i = int(np.argmax(score * prior))
    if score[i] <= 0.05:
        return 0.0
    L = float(lags[i])
    if 0 < i < len(lags) - 1:
        a, b, c = ac[lags[i] - 1], ac[lags[i]], ac[lags[i] + 1]
        d = a - 2 * b + c
        if d < 0:
            L += 0.5 * (a - c) / d
    return 60 * fps / L


def signature(window: np.ndarray, rate: int = DEFAULT_RATE) -> dict:
    x = np.asarray(window, np.float64).reshape(-1)
    rms = float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
    db = 20 * math.log10(max(rms, 1e-9))
    energy = min(1.0, max(0.0, (db + 50.0) / 44.0))

    n = 1 << int(math.ceil(math.log2(max(1024, rate * 0.093))))  # ~93 ms: enough resolution for 55 Hz notes
    mag = np.abs(np.fft.rfft(_frames(x, n, n // 2), axis=1))
    freqs = np.fft.rfftfreq(n, 1.0 / rate)

    total = mag.sum(axis=1)
    loud = total > 1e-9
    if loud.any():
        cent = (mag[loud] @ freqs) / total[loud]
        c = float(np.mean(cent))
        brightness = (math.log(max(c, CENTROID_LO)) - math.log(CENTROID_LO)) / (math.log(CENTROID_HI) - math.log(CENTROID_LO))
        brightness = min(1.0, max(0.0, brightness))
    else:
        brightness = 0.0

    band = (freqs >= CHROMA_LO) & (freqs <= CHROMA_HI)
    pc = (np.round(12 * np.log2(freqs[band] / 440.0)).astype(int) + 9) % 12  # C = 0, A = 9
    per_bin = (mag[:, band] ** 2).sum(axis=0)  # power: tonal peaks stand out from drums and noise
    chroma = np.bincount(pc, weights=per_bin, minlength=12)
    norm = np.linalg.norm(chroma)
    chroma = chroma / norm if norm > 0 else np.zeros(12)

    return {
        "tempo_bpm": round(float(_tempo(x.astype(np.float32), rate)), 2),
        "energy": round(energy, 4),
        "brightness": round(brightness, 4),
        "chroma": [round(float(v), 4) for v in chroma],
    }


def tempo_distance(a: float, b: float) -> float | None:
    """0 for the same (or double/half) tempo, 1 for clearly different. None if either is unknown."""
    if not a or not b or a <= 0 or b <= 0:
        return None
    r = abs(math.log2(a / b))
    r = abs(r - round(r))  # octave-aware: 60 vs 120 bpm → 0
    return min(1.0, r / TEMPO_SCALE_OCTAVES)


def distance(a: dict, b: dict) -> float:
    ca, cb = np.asarray(a.get("chroma") or [0] * 12, float), np.asarray(b.get("chroma") or [0] * 12, float)
    na, nb = np.linalg.norm(ca), np.linalg.norm(cb)
    parts = {
        "chroma": (1.0 - float(ca @ cb / (na * nb))) / CHROMA_SCALE if na > 0 and nb > 0 else 1.0,
        "tempo": tempo_distance(a.get("tempo_bpm", 0), b.get("tempo_bpm", 0)),
        "brightness": abs(a.get("brightness", 0) - b.get("brightness", 0)),
        "energy": abs(a.get("energy", 0) - b.get("energy", 0)),
    }
    used = {k: v for k, v in parts.items() if v is not None}
    weight = sum(WEIGHTS[k] for k in used)
    d = sum(WEIGHTS[k] * min(1.0, max(0.0, v)) for k, v in used.items()) / weight
    return round(min(1.0, max(0.0, d)), 4)
