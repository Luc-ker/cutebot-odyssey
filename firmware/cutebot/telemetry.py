"""T17 - Cutebot telemetry: T,<dist_cm>,<lineL>,<lineR>,<override> at 10 Hz max."""
INTERVAL_MS = 100
CHANGE_GAP_MS = 30  # an override change may go out sooner, but never faster than this


class Telemetry:
    def __init__(self, send):
        self._send = send
        self._last_t = None
        self._last_override = None

    def maybe_send(self, now_ms, distance_cm, line, override):
        ov = 1 if override else 0
        if self._last_t is not None:
            gap = now_ms - self._last_t
            changed = ov != self._last_override
            if gap < INTERVAL_MS and not (changed and gap >= CHANGE_GAP_MS):
                return False
        d = 400 if distance_cm is None else max(0, min(400, int(round(distance_cm))))
        self._send("T,%d,%d,%d,%d" % (d, 1 if line[0] else 0, 1 if line[1] else 0, ov))
        self._last_t = now_ms
        self._last_override = ov
        return True
