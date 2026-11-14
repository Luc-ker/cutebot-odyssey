"""Audio input capture (T64, whitepaper §7.6).

C7: ``AudioInput(config).start()``, ``.on_block(cb(samples_float32, ts))``, ``.last(seconds) -> ndarray``,
``.rate``.

- Live mode: ``sounddevice`` input stream, device ``AUDIO_DEVICE`` (name substring or index), mono,
  ``AUDIO_RATE``, blocks of ~23 ms.
- File mode: ``AudioInput(config, file="song.wav")`` (or env ``GENRATOR_AUDIO_FILE``) plays a WAV file
  into the pipeline in real time, for tests and for demos without a microphone. ``realtime=False``
  feeds it as fast as possible (tests).
- Keeps the last 30 s in a ring buffer in memory. **Audio is never written to disk.**

Block callbacks run on the audio thread: keep them short, and hop to the asyncio loop with
``loop.call_soon_threadsafe`` / ``asyncio.run_coroutine_threadsafe`` to publish.
``ts`` is the Unix time of the *last* sample in the block.

CLI: ``python -m server.audio.capture [--file song.wav] [--seconds 10]`` prints a live level meter.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import wave
from typing import Callable

import numpy as np

log = logging.getLogger(__name__)

RING_SECONDS = 30.0
BLOCK_SECONDS = 0.023
DEFAULT_RATE = 44100

BlockCallback = Callable[[np.ndarray, float], None]


def read_wav(path: str) -> tuple[np.ndarray, int]:
    """WAV file -> (mono float32 in [-1, 1], rate). PCM 8/16/24/32-bit (stdlib ``wave``)."""
    with wave.open(path, "rb") as w:
        rate, ch, width, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if width == 1:
        x = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128.0) / 128.0
    elif width == 2:
        x = np.frombuffer(raw, "<i2").astype(np.float32) / 32768.0
    elif width == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        v = np.where(v & 0x800000, v - 0x1000000, v)
        x = v.astype(np.float32) / 8388608.0
    elif width == 4:
        x = np.frombuffer(raw, "<i4").astype(np.float32) / 2147483648.0
    else:  # pragma: no cover
        raise ValueError(f"unsupported WAV sample width {width}")
    return x.reshape(-1, ch).mean(axis=1).astype(np.float32), rate


def resample(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Linear-interpolation resample. Good enough for feeding the pipeline from a file."""
    if src == dst or len(x) == 0:
        return x.astype(np.float32, copy=False)
    n = int(round(len(x) * dst / src))
    t = np.arange(n, dtype=np.float64) * (src / dst)
    return np.interp(t, np.arange(len(x)), x).astype(np.float32)


class RingBuffer:
    """Fixed-size float32 ring; thread-safe writes and snapshot reads."""

    def __init__(self, size: int):
        self.buf = np.zeros(size, np.float32)
        self.size = size
        self.pos = 0  # next write index
        self.filled = 0
        self.lock = threading.Lock()

    def write(self, x: np.ndarray) -> None:
        x = x[-self.size:]
        n = len(x)
        with self.lock:
            end = self.pos + n
            if end <= self.size:
                self.buf[self.pos:end] = x
            else:
                k = self.size - self.pos
                self.buf[self.pos:] = x[:k]
                self.buf[: n - k] = x[k:]
            self.pos = end % self.size
            self.filled = min(self.size, self.filled + n)

    def last(self, n: int) -> np.ndarray:
        with self.lock:
            n = max(0, min(n, self.filled))
            start = (self.pos - n) % self.size
            if start + n <= self.size:
                return self.buf[start:start + n].copy()
            return np.concatenate([self.buf[start:], self.buf[: (start + n) % self.size]])

    def clear(self) -> None:
        with self.lock:
            self.pos = self.filled = 0


def _parse_device(dev):
    if dev is None or dev == "":
        return None
    if isinstance(dev, int):
        return dev
    s = str(dev).strip()
    return int(s) if s.lstrip("-").isdigit() else s


class AudioInput:
    def __init__(self, config: dict | None = None, file: str | None = None, realtime: bool = True,
                 block_seconds: float = BLOCK_SECONDS):
        config = config or {}
        self.file = file or os.environ.get("GENRATOR_AUDIO_FILE") or None
        self.realtime = realtime
        self.device = _parse_device(config.get("AUDIO_DEVICE"))
        self.rate = int(config.get("AUDIO_RATE") or DEFAULT_RATE)
        self.blocksize = max(64, int(round(self.rate * block_seconds)))
        self._ring = RingBuffer(int(RING_SECONDS * self.rate))
        self._callbacks: list[BlockCallback] = []
        self._stream = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._done = threading.Event()

    # ---- C7 ------------------------------------------------------------------------------------
    def on_block(self, cb: BlockCallback) -> None:
        self._callbacks.append(cb)

    def last(self, seconds: float) -> np.ndarray:
        return self._ring.last(int(round(seconds * self.rate)))

    def start(self) -> "AudioInput":
        self._stop.clear()
        self._done.clear()
        if self.file:
            self._start_file()
        else:
            self._start_device()
        return self

    # ---- extras ----------------------------------------------------------------------------------
    def stop(self) -> None:
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
        self._done.set()

    def wait(self, timeout: float | None = None) -> bool:
        """File mode: block until the whole file has been fed. Returns False on timeout."""
        return self._done.wait(timeout)

    def clear(self) -> None:
        """Forget buffered audio (used by ``system.reset``)."""
        self._ring.clear()

    def feed(self, block: np.ndarray, ts: float | None = None) -> None:
        """Push samples as if captured now. Used by file mode and by tests."""
        block = np.asarray(block, np.float32).reshape(-1)
        self._ring.write(block)
        ts = time.time() if ts is None else ts
        for cb in list(self._callbacks):
            try:
                cb(block, ts)
            except Exception:  # one bad consumer must not kill capture
                log.exception("audio block callback failed")

    # ---- sources -------------------------------------------------------------------------------
    def _start_device(self) -> None:
        import sounddevice as sd  # lazy: tests and file mode don't need PortAudio

        def callback(indata, frames, time_info, status):
            if status:
                log.debug("audio status: %s", status)
            self.feed(indata[:, 0].copy())

        self._stream = sd.InputStream(device=self.device, channels=1, samplerate=self.rate,
                                      blocksize=self.blocksize, dtype="float32", callback=callback)
        self._stream.start()
        log.info("audio input: device=%r rate=%d block=%d", self.device, self.rate, self.blocksize)

    def _start_file(self) -> None:
        samples, src_rate = read_wav(self.file)
        samples = resample(samples, src_rate, self.rate)
        log.info("audio input: file %s (%.1f s)", self.file, len(samples) / self.rate)

        def run():
            t0 = time.monotonic()
            wall0 = time.time()
            bs = self.blocksize
            for i in range(0, len(samples), bs):
                if self._stop.is_set():
                    break
                block = samples[i:i + bs]
                end_s = (i + len(block)) / self.rate
                if self.realtime:
                    delay = t0 + end_s - time.monotonic()
                    if delay > 0:
                        time.sleep(delay)
                    self.feed(block)
                else:
                    self.feed(block, wall0 + end_s)
            self._done.set()

        self._thread = threading.Thread(target=run, name="audio-file", daemon=True)
        self._thread.start()


def _meter(argv: list[str] | None = None) -> None:
    import argparse

    p = argparse.ArgumentParser(description="Live input level meter (nothing is recorded).")
    p.add_argument("--file", help="play a WAV file into the pipeline instead of the microphone")
    p.add_argument("--device", help="AUDIO_DEVICE override (name or index)")
    p.add_argument("--rate", type=int, default=DEFAULT_RATE)
    p.add_argument("--seconds", type=float, default=10.0)
    a = p.parse_args(argv)
    audio = AudioInput({"AUDIO_DEVICE": a.device, "AUDIO_RATE": a.rate}, file=a.file).start()
    end = time.time() + a.seconds
    try:
        while time.time() < end and not (a.file and audio.wait(0)):
            x = audio.last(0.1)
            rms = float(np.sqrt(np.mean(x * x))) if len(x) else 0.0
            db = 20 * np.log10(max(rms, 1e-6))
            print(f"\r{db:6.1f} dBFS |{'#' * int(max(0, db + 60) / 1.5):<40}|", end="", flush=True)
            time.sleep(0.1)
    finally:
        audio.stop()
        print()


if __name__ == "__main__":
    _meter()
