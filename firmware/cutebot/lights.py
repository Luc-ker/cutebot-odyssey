"""T15 - Cutebot light effects engine (non-blocking).

Headlights: I2C 0x10, register 0x04 = left, 0x08 = right, payload [reg, r, g, b]
(CHECK against vendor library). Modes: S solid (sets base), F flash, P pulse.
"""


def hw_writer(i2c=None):
    if i2c is None:
        from microbit import i2c as hw
        i2c = hw

    def write(r, g, b):
        i2c.write(0x10, bytes([0x04, r, g, b]))
        i2c.write(0x10, bytes([0x08, r, g, b]))

    return write


def _lerp(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


class Lights:
    def __init__(self, writer=None):
        self._w = writer if writer is not None else hw_writer()
        self.base = (0, 0, 0)
        self._mode = None
        self._rgb = (0, 0, 0)
        self._start = 0
        self._ms = 1
        self._last = None

    def apply(self, cmd, now_ms=0):
        mode = str(cmd["mode"])[:1].upper()
        rgb = tuple(int(c) & 255 for c in cmd["rgb"])
        if mode == "S":
            self.base = rgb
            self._mode = None
        else:
            self._mode = mode
            self._rgb = rgb
            self._start = now_ms
            self._ms = max(1, int(cmd.get("ms", 0)))
        self.tick(now_ms)

    def tick(self, now_ms):
        colour = self.base
        if self._mode is not None:
            dt = now_ms - self._start
            if dt >= self._ms:
                self._mode = None
            elif self._mode == "F":
                colour = self._rgb
            else:  # pulse: base -> rgb -> base, triangle shaped
                f = dt / self._ms
                colour = _lerp(self.base, self._rgb, 1 - abs(2 * f - 1))
        if colour != self._last:
            self._w(colour[0], colour[1], colour[2])
            self._last = colour
