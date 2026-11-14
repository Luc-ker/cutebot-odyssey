"""Audio features (T66, whitepaper §7.6, §7.9).

Every 50 ms publish ``audio.features {rms, energy, brightness, silent}`` (C3), 20 Hz:

- ``rms``: RMS of the last 50 ms.
- ``energy`` (0-1): RMS divided by an adaptive running peak with a slow release, so the room's
  playback level doesn't matter: the loudest recent part of the song is ~1, quiet passages are lower.
- ``brightness`` (0-1): spectral centroid on a log scale from 150 Hz (0) to 8 kHz (1).
  Bright and airy music is high, dark and heavy music is low.
- ``silent``: from the silence gate (T67).
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

import numpy as np

from server.audio.silence import SilenceGate

HOP_S = 0.05
FFT_N = 2048
PEAK_RELEASE_TAU_S = 20.0  # how fast the running peak forgets a loud moment
PEAK_FLOOR = 0.01          # don't call room noise "full energy" after a long quiet spell
CENTROID_LO, CENTROID_HI = 150.0, 8000.0
GATE_WINDOW_HOPS = 10      # the gate hears the RMS of the last 0.5 s, so gaps between hits aren't "silence"


def spectral_centroid(x: np.ndarray, rate: int) -> float:
    """Magnitude-weighted mean frequency in Hz (0 for digital silence)."""
    if len(x) == 0:
        return 0.0
    n = min(FFT_N, len(x))
    mag = np.abs(np.fft.rfft(x[-n:] * np.hanning(n)))
    total = mag.sum()
    if total <= 1e-12:
        return 0.0
    freqs = np.fft.rfftfreq(n, 1.0 / rate)
    return float((freqs * mag).sum() / total)


def brightness_from_centroid(c: float) -> float:
    if c <= 0:
        return 0.0
    b = (math.log(c) - math.log(CENTROID_LO)) / (math.log(CENTROID_HI) - math.log(CENTROID_LO))
    return float(min(1.0, max(0.0, b)))


class AudioFeatures:
    """Feed blocks with :meth:`process`; get one feature dict per 50 ms hop."""

    def __init__(self, rate: int, gate: SilenceGate | None = None):
        self.rate = rate
        self.hop = int(round(rate * HOP_S))
        self.gate = gate or SilenceGate()
        self.reset()

    def reset(self) -> None:
        self._pending = np.zeros(0, np.float32)
        self._history = np.zeros(FFT_N, np.float32)  # for the FFT window, longer than one hop
        self._peak = PEAK_FLOOR
        self._powers: list[float] = []
        self.gate.reset()

    def process(self, samples: np.ndarray, ts: float) -> list[dict]:
        """``ts`` = Unix time of the last sample in ``samples``."""
        x = np.concatenate([self._pending, np.asarray(samples, np.float32)])
        out = []
        n_hops = len(x) // self.hop
        for i in range(n_hops):
            frame = x[i * self.hop:(i + 1) * self.hop]
            frame_ts = ts - (len(x) - (i + 1) * self.hop) / self.rate
            out.append(self._frame(frame, frame_ts))
        self._pending = x[n_hops * self.hop:]
        return out

    def _frame(self, frame: np.ndarray, ts: float) -> dict:
        self._history = np.concatenate([self._history, frame])[-FFT_N:]
        rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))
        decay = math.exp(-HOP_S / PEAK_RELEASE_TAU_S)
        self._peak = max(rms, self._peak * decay, PEAK_FLOOR)
        self._powers = (self._powers + [rms * rms])[-GATE_WINDOW_HOPS:]
        silent = self.gate.update(math.sqrt(sum(self._powers) / len(self._powers)), ts)
        return {
            "rms": round(rms, 5),
            "energy": round(min(1.0, rms / self._peak), 4),
            "brightness": round(brightness_from_centroid(spectral_centroid(self._history, self.rate)), 4),
            "silent": bool(silent),
            "_ts": ts,  # internal; stripped before publishing
        }


async def run(hub: Any, config: dict | None = None, audio=None) -> None:
    """Brain entrypoint (C7). Pass the shared ``AudioInput`` as ``audio``; one is made if absent."""
    if audio is None:
        from server.audio.capture import AudioInput
        audio = AudioInput(config or {}).start()
    loop = asyncio.get_running_loop()
    feats = AudioFeatures(audio.rate)

    def on_block(samples, ts):  # audio thread
        for f in feats.process(samples, ts):
            f.pop("_ts", None)
            asyncio.run_coroutine_threadsafe(hub.pub("audio.features", f), loop)

    async def on_reset(_env):
        feats.reset()

    hub.sub("system.reset", on_reset)
    audio.on_block(on_block)
    await asyncio.Event().wait()
