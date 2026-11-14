"""T19 - gamepad buttons -> B,<L|H|S|R> packets.

Pin map (joystick:bit, CHECK the cap colours on your board and fix the comment):
  P12 -> L Light | P13 -> H Horn | P14 -> S Shout | P15 -> R Reset (long press only, 1.5 s)
Buttons are active-low with pull-ups. Each action is sent 3 times, 20 ms apart (radio is lossy);
the bridge (T21) de-duplicates.
"""
KEYS = ("L", "H", "S", "R")
DEBOUNCE_MS = 30
REPEATS = 3
GAP_MS = 20
LONG_MS = 1500


def hw_read():
    from microbit import pin12, pin13, pin14, pin15
    pins = {"L": pin12, "H": pin13, "S": pin14, "R": pin15}
    for p in pins.values():
        p.set_pull(p.PULL_UP)
    return lambda: {k: p.read_digital() == 0 for k, p in pins.items()}


class Buttons:
    def __init__(self, send, debounce_ms=DEBOUNCE_MS, repeats=REPEATS, gap_ms=GAP_MS, long_ms=LONG_MS):
        self._send = send
        self.debounce_ms = debounce_ms
        self.repeats = repeats
        self.gap_ms = gap_ms
        self.long_ms = long_ms
        self._raw = dict((k, False) for k in KEYS)
        self._chg = dict((k, 0) for k in KEYS)
        self._stable = dict((k, False) for k in KEYS)
        self._down = dict((k, 0) for k in KEYS)
        self._long_sent = dict((k, False) for k in KEYS)
        self._pending = []
        self.fired = []  # one entry per action (not per radio repeat)

    def update(self, now, states):
        for k in KEYS:
            raw = bool(states.get(k, False))
            if raw != self._raw[k]:
                self._raw[k] = raw
                self._chg[k] = now
            if raw != self._stable[k] and now - self._chg[k] >= self.debounce_ms:
                self._stable[k] = raw
                if raw:
                    self._down[k] = now
                    self._long_sent[k] = False
                    if k != "R":
                        self._fire(k, now)
            if k == "R" and self._stable[k] and not self._long_sent[k] and now - self._down[k] >= self.long_ms:
                self._long_sent[k] = True
                self._fire(k, now)
        self._flush(now)

    def _fire(self, k, now):
        self.fired.append(k)
        self._pending.append([now, "B," + k, self.repeats])

    def _flush(self, now):
        keep = []
        for item in self._pending:
            if now >= item[0]:
                self._send(item[1])
                item[2] -= 1
                item[0] += self.gap_ms
            if item[2] > 0:
                keep.append(item)
        self._pending = keep
