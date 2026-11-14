"""T13 - ultrasonic safety stop.

Cutebot: trigger P8, echo P12 (CHECK against vendor docs).
"""
SAFETY_STOP_CM = 8  # keep equal to shared/config.json SAFETY_STOP_CM


def gate(throttle, distance_cm, stop_cm=SAFETY_STOP_CM):
    """Refuse forward motion inside stop_cm. Reversing is always allowed."""
    if distance_cm is not None and distance_cm < stop_cm and throttle > 0:
        return 0
    return throttle


def _median(vals):
    s = sorted(vals)
    return s[len(s) // 2]


class Sonar:
    def __init__(self, read_raw=None):
        self._raw = read_raw if read_raw is not None else hw_reader()
        self._hist = []
        self.latest = None

    def read_cm(self):
        v = self._raw()
        if v and v > 0:  # ignore 0 / timeouts
            self._hist.append(v)
            self._hist = self._hist[-3:]
        if self._hist:
            self.latest = _median(self._hist)
        return self.latest


def hw_reader():
    from microbit import pin8, pin12
    from machine import time_pulse_us
    from utime import sleep_us

    def read():
        pin8.write_digital(0)
        sleep_us(2)
        pin8.write_digital(1)
        sleep_us(10)
        pin8.write_digital(0)
        t = time_pulse_us(pin12, 1, 15000)  # ~2.5 m max
        if t < 0:
            return 0
        return t // 58  # microseconds -> cm

    return read
