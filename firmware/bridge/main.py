"""T21 - bridge micro:bit: laptop (USB serial, 115200) <-> robot/gamepad (radio).

 serial line -> radio : any packet that passes the codec (L lights, R recoil, V rumble ...)
 radio T / B  -> serial: telemetry and buttons; repeated B within 150 ms are collapsed
 radio D      -> dropped (gamepad -> robot traffic; keeps the serial line quiet)
"""
RADIO_GROUP = 42   # keep equal to shared/config.json RADIO_GROUP
RADIO_CHANNEL = 7  # keep equal to shared/config.json RADIO_CHANNEL
DEDUPE_MS = 150

_FIELDS = {"D": 4, "B": 2, "L": 6, "R": 2, "V": 2, "T": 5}


def _valid(s):
    """Local stand-in for the T05 codec: shape and numeric checks only."""
    try:
        p = s.split(",")
        n = _FIELDS.get(p[0])
        if n is None or len(p) != n or len(s) > 32:
            return False
        if p[0] == "B":
            return p[1] in ("L", "H", "S", "R")
        nums = p[2:] if p[0] == "L" else p[1:]
        if p[0] == "L" and p[1] not in ("S", "F", "P"):
            return False
        for x in nums:
            int(x)
        return True
    except Exception:
        return False


try:
    from codec import decode as _decode

    def valid(s):
        return _decode(s) is not None
except ImportError:
    valid = _valid


class Bridge:
    def __init__(self, serial_write, radio_send, is_valid=valid, dedupe_ms=DEDUPE_MS):
        self._serial_write = serial_write
        self._radio_send = radio_send
        self._valid = is_valid
        self._dedupe = dedupe_ms
        self._last_b = {}

    def from_serial(self, line):
        s = line.strip()
        if s and self._valid(s):
            self._radio_send(s)
            return True
        return False

    def from_radio(self, msg, now):
        kind = msg[:1]
        if kind == "T":
            self._serial_write(msg + "\n")
            return True
        if kind == "B":
            last = self._last_b.get(msg)
            if last is not None and now - last < self._dedupe:
                return False          # measured from the last FORWARDED copy, so bursts collapse
            self._last_b[msg] = now
            self._serial_write(msg + "\n")
            return True
        return False


def main():
    from microbit import running_time, sleep, uart
    import radio

    radio.config(group=RADIO_GROUP, channel=RADIO_CHANNEL, length=32, queue=8)
    radio.on()
    uart.init(115200)  # default pins = the USB serial link
    bridge = Bridge(lambda s: uart.write(s), radio.send)
    buf = b""
    while True:
        if uart.any():
            buf += uart.read() or b""
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    bridge.from_serial(line.decode())
                except Exception:
                    pass
            if len(buf) > 128:
                buf = b""
        while True:
            msg = radio.receive()
            if msg is None:
                break
            bridge.from_radio(msg, running_time())
        sleep(2)


if __name__ == "__main__":
    main()
