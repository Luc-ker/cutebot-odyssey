"""Clip store for Gemini (T68, whitepaper §7.6, §7.7, §11).

C7: ``ClipStore(audio_input).get_clip(seconds) -> bytes | None``: a 16 kHz mono 16-bit WAV of the last
``seconds`` of audio, built in memory.

- Resampled with an FFT (band-limited, so no aliasing) to 16 kHz.
- Leading and trailing silence trimmed; peak-normalised to -0.4 dBFS.
- If more than 70 % of the clip is silent, returns None, and the caller skips the Gemini call.
- Nothing is kept: no cache and no file. The bytes go to the caller and nowhere else.
"""

from __future__ import annotations

import io
import wave

import numpy as np

TARGET_RATE = 16000
FRAME_S = 0.02
MAX_SILENT_FRACTION = 0.7
ABS_SILENCE_RMS = 0.003   # ~ -50 dBFS
REL_SILENCE_DB = -40.0    # a frame 40 dB under the loudest frame is silence too
PEAK = 0.95
MIN_SECONDS = 0.5


def resample_fft(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Band-limited resample via the real FFT (an ideal low-pass at the lower Nyquist)."""
    if src == dst or len(x) == 0:
        return np.asarray(x, np.float32)
    n_out = int(round(len(x) * dst / src))
    spec = np.fft.rfft(np.asarray(x, np.float64))
    k = n_out // 2 + 1
    if len(spec) >= k:
        spec = spec[:k]
    else:
        spec = np.concatenate([spec, np.zeros(k - len(spec), spec.dtype)])
    return (np.fft.irfft(spec, n_out) * (n_out / len(x))).astype(np.float32)


def silent_frames(x: np.ndarray, rate: int) -> np.ndarray:
    """Boolean mask, one entry per 20 ms frame."""
    n = max(1, int(rate * FRAME_S))
    m = len(x) // n
    if m == 0:
        return np.ones(1, bool)
    rms = np.sqrt(np.mean(x[: m * n].astype(np.float64).reshape(m, n) ** 2, axis=1))
    threshold = max(ABS_SILENCE_RMS, rms.max() * 10 ** (REL_SILENCE_DB / 20))
    return rms < threshold


def to_wav(x: np.ndarray, rate: int) -> bytes:
    pcm = (np.clip(x, -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def make_clip(x: np.ndarray, rate: int) -> bytes | None:
    """Pure version of :meth:`ClipStore.get_clip` for a given buffer."""
    x = np.asarray(x, np.float32)
    if len(x) < MIN_SECONDS * rate:
        return None
    mask = silent_frames(x, rate)
    if mask.mean() > MAX_SILENT_FRACTION:
        return None
    n = int(rate * FRAME_S)
    loud = np.flatnonzero(~mask)
    x = x[loud[0] * n: (loud[-1] + 1) * n]
    y = resample_fft(x, rate, TARGET_RATE)
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    if peak > 0:
        y = y * (PEAK / peak)
    return to_wav(y, TARGET_RATE)


class ClipStore:
    def __init__(self, audio_input):
        self.audio = audio_input

    def get_clip(self, seconds: float) -> bytes | None:
        return make_clip(self.audio.last(seconds), self.audio.rate)
