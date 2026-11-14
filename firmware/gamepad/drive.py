"""T18 - gamepad joystick drive sender (25 Hz default, radio only).

joystick:bit: X on P1, Y on P2 (CHECK pins and which direction raises the reading, then set the
SIGN constants below). Output packet: D,<throttle>,<turn>,<seq>.
"""
DRIVE_HZ = 25      # shared/config.json DRIVE_HZ
DEAD = 0.08
SPAN = 480.0       # raw counts from centre treated as full deflection (margin for noisy ends)
Y_FORWARD_SIGN = 1   # +1 if pushing the stick forward RAISES the Y reading
X_RIGHT_SIGN = 1     # +1 if pushing the stick right RAISES the X reading


def _shape(v):
    """-1..1 with dead-zone, rescaled so it ramps from 0, and a gentle curve for fine control."""
    a = abs(v)
    if a < DEAD:
        return 0.0
    a = min(1.0, (a - DEAD) / (1.0 - DEAD))
    a = 0.6 * a + 0.4 * a * a
    return a if v > 0 else -a


def axes_to_drive(raw_x, raw_y, centre):
    cx, cy = centre
    x = max(-1.0, min(1.0, (raw_x - cx) * X_RIGHT_SIGN / SPAN))
    y = max(-1.0, min(1.0, (raw_y - cy) * Y_FORWARD_SIGN / SPAN))
    return int(round(_shape(y) * 100)), int(round(_shape(x) * 100))


def format_drive(throttle, turn, seq):
    return "D,%d,%d,%d" % (throttle, turn, seq & 255)


def hw_read_xy():
    from microbit import pin1, pin2
    return pin1.read_analog(), pin2.read_analog()


class DriveSender:
    def __init__(self, read_xy, send, hz=DRIVE_HZ):
        self._read = read_xy
        self._send = send
        self._period = 1000 // hz
        self._last = None
        self.seq = 0
        self.centre = (512, 512)

    def calibrate(self, samples=10):
        sx = sy = 0
        for _ in range(samples):
            x, y = self._read()
            sx += x
            sy += y
        self.centre = (sx // samples, sy // samples)

    def tick(self, now_ms):
        """Send one packet if due. Zeros are sent too, so the robot's failsafe stays fed."""
        if self._last is not None and now_ms - self._last < self._period:
            return False
        self._last = now_ms
        x, y = self._read()
        t, r = axes_to_drive(x, y, self.centre)
        self._send(format_drive(t, r, self.seq))
        self.seq = (self.seq + 1) & 255
        return True
