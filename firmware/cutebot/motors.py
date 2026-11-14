"""T11 - Cutebot motor driver.

I2C address 0x10; register 0x01 = left wheel, 0x02 = right wheel,
payload [reg, direction(0 fwd / 1 back), speed 0-100, 0].
CHECK these bytes against the ELECFREAKS vendor library before first run.
"""
ADDR = 0x10
REG_LEFT = 0x01
REG_RIGHT = 0x02


def _clamp(v, lo=-100, hi=100):
    return lo if v < lo else hi if v > hi else v


def mix(throttle, turn):
    """Differential mix. Turn > 0 turns right (left wheel faster)."""
    t = _clamp(throttle)
    r = _clamp(turn)
    left = t + r
    right = t - r
    biggest = max(abs(left), abs(right))
    if biggest > 100:  # scale both so the ratio (the steering) is kept
        left = left * 100 / biggest
        right = right * 100 / biggest
    return int(round(left)), int(round(right))


class Motors:
    def __init__(self, i2c=None):
        if i2c is None:
            from microbit import i2c as hw
            i2c = hw
        self._i2c = i2c

    def _wheel(self, reg, speed):
        direction = 0 if speed >= 0 else 1
        self._i2c.write(ADDR, bytes([reg, direction, min(100, abs(int(speed))), 0]))

    def set_drive(self, throttle, turn):
        left, right = mix(throttle, turn)
        self._wheel(REG_LEFT, left)
        self._wheel(REG_RIGHT, right)
        return left, right

    def stop(self):
        self._wheel(REG_LEFT, 0)
        self._wheel(REG_RIGHT, 0)
