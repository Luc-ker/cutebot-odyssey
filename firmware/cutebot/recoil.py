"""T16 - automatic recoil: reverse for the first 60 % of ms, then turn in place."""
try:
    from microbit import running_time as _now
except ImportError:
    import time

    def _now():
        return int(time.time() * 1000)

REVERSE_SPEED = -60
TURN_SPEED = 70
REVERSE_FRACTION = 0.6

_start = None
_ms = 0


def reset():
    global _start, _ms
    _start = None
    _ms = 0


def start_recoil(ms, now_ms=None):
    """A second call while active restarts the timer (no stacking)."""
    global _start, _ms
    _start = _now() if now_ms is None else now_ms
    _ms = max(1, int(ms))


def active(now_ms=None):
    now = _now() if now_ms is None else now_ms
    return _start is not None and 0 <= now - _start < _ms


def command(now_ms=None):
    """(throttle, turn) to use instead of the joystick while active."""
    now = _now() if now_ms is None else now_ms
    if not active(now):
        return 0, 0
    if (now - _start) / _ms < REVERSE_FRACTION:
        return REVERSE_SPEED, 0
    return 0, TURN_SPEED
