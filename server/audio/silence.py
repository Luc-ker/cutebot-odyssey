"""Silence gate (T67, whitepaper §7.9).

C7: ``SilenceGate().update(rms, ts) -> bool`` (True = silent).

- **Adaptive noise floor.** The floor follows the quietest recent level: it falls quickly whenever the
  input gets quieter, and only rises (slowly) while we are already silent, so long stretches of music
  never teach the gate that music is "noise". The floor is capped, so even a gate started over loud
  music finds its way to a sane threshold.
- **Hysteresis.** Silent after 1.5 s continuously below the threshold; loud again after 0.3 s
  continuously above it.

Feed it RMS of short frames (~20-50 ms) of float audio in [-1, 1].
"""

from __future__ import annotations

import math

SILENT_AFTER_S = 1.5
LOUD_AFTER_S = 0.3
THRESHOLD_RATIO = 3.0      # ~ +10 dB over the noise floor
ABS_MIN_THRESHOLD = 0.0015  # ~ -56 dBFS: below this it is silence whatever the floor says
MAX_FLOOR = 0.005           # ~ -46 dBFS: the room is never assumed noisier than this
FLOOR_FALL_TAU_S = 0.3
FLOOR_RISE_TAU_S = 5.0


class SilenceGate:
    def __init__(self, start_silent: bool = True):
        self.silent = start_silent
        self.floor: float | None = None
        self._last_ts: float | None = None
        self._cross_since: float | None = None  # when the level crossed to the other side

    @property
    def threshold(self) -> float:
        floor = self.floor if self.floor is not None else MAX_FLOOR
        return max(ABS_MIN_THRESHOLD, floor * THRESHOLD_RATIO)

    def update(self, rms: float, ts: float) -> bool:
        rms = max(0.0, float(rms))
        dt = 0.0 if self._last_ts is None else max(0.0, ts - self._last_ts)
        self._last_ts = ts
        self._update_floor(rms, dt)

        above = rms > self.threshold
        if above == (not self.silent):
            self._cross_since = None  # level agrees with the current state
        else:
            if self._cross_since is None:
                self._cross_since = ts
            needed = LOUD_AFTER_S if self.silent else SILENT_AFTER_S
            if ts - self._cross_since >= needed:
                self.silent = not self.silent
                self._cross_since = None
        return self.silent

    def _update_floor(self, rms: float, dt: float) -> None:
        if self.floor is None:
            self.floor = min(rms, MAX_FLOOR)
            return
        if rms < self.floor:
            a = 1.0 - math.exp(-dt / FLOOR_FALL_TAU_S) if dt else 1.0
            self.floor += (rms - self.floor) * a
        elif self.silent:
            a = 1.0 - math.exp(-dt / FLOOR_RISE_TAU_S)
            self.floor += (min(rms, MAX_FLOOR) - self.floor) * a
        self.floor = min(max(self.floor, 1e-6), MAX_FLOOR)

    def reset(self, start_silent: bool = True) -> None:
        self.__init__(start_silent)
