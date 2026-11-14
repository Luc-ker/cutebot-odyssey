"""T20 (P2) - gamepad rumble: V,<ms> runs the joystick:bit vibration motor (P16), cap 1000 ms."""
MAX_MS = 1000


def hw_motor():
    from microbit import pin16
    return lambda on: pin16.write_digital(1 if on else 0)


class Rumble:
    def __init__(self, motor):
        self._motor = motor
        self._end = None
        self._on = False

    def start(self, ms, now):
        ms = min(max(0, int(ms)), MAX_MS)
        if ms == 0:
            return
        end = now + ms
        if self._on and end <= self._end:  # ignore unless longer
            return
        self._end = end
        self._on = True
        self._motor(True)

    def on_packet(self, pkt, now):
        if pkt.get("type") == "V":
            self.start(pkt["ms"], now)

    def tick(self, now):
        if self._on and now >= self._end:
            self._on = False
            self._motor(False)
