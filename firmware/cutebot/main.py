"""T12 - Cutebot radio receiver, dispatch and failsafe stop.

Dispatch (Controller) is separate from radio I/O (main) so it can be tested on a laptop.
Packets: D drive, L lights, R recoil (contract C6).

ASSUMPTION (reconcile with T05's firmware codec): decode() returns dicts like
 {"type":"D","throttle":int,"turn":int,"seq":int}, {"type":"L","mode":"S|F|P","rgb":[r,g,b],"ms":int},
 {"type":"R","ms":int}. A small local fallback decoder is used if `codec` is not on the device.
"""
RADIO_GROUP = 42   # keep equal to shared/config.json RADIO_GROUP
RADIO_CHANNEL = 7  # keep equal to shared/config.json RADIO_CHANNEL
FAILSAFE_MS = 300  # shared/config.json FAILSAFE_MS
SONAR_PERIOD_MS = 100

try:
    from codec import decode
except ImportError:
    def decode(s):
        try:
            p = s.split(",")
            k = p[0]
            if k == "D" and len(p) == 4:
                return {"type": "D", "throttle": int(p[1]), "turn": int(p[2]), "seq": int(p[3])}
            if k == "L" and len(p) == 6:
                return {"type": "L", "mode": p[1], "rgb": [int(p[2]), int(p[3]), int(p[4])], "ms": int(p[5])}
            if k == "R" and len(p) == 2:
                return {"type": "R", "ms": int(p[1])}
        except Exception:
            pass
        return None


def seq_newer(new, last):
    """Wrap-aware: True if `new` is ahead of `last` by 1..127 (mod 256)."""
    d = (new - last) & 0xFF
    return 0 < d < 128


class Controller:
    def __init__(self, motors, lights, start_recoil, recoil_active, recoil_command,
                 sonar_gate=None, edge_gate=None, failsafe_ms=FAILSAFE_MS):
        self.motors = motors
        self.lights = lights
        self._start_recoil = start_recoil
        self._recoil_active = recoil_active
        self._recoil_command = recoil_command
        self._sonar_gate = sonar_gate
        self._edge_gate = edge_gate
        self.failsafe_ms = failsafe_ms
        self.last_seq = None
        self.last_drive_ms = None
        self.throttle = 0
        self.turn = 0
        self.distance = None
        self.line = (0, 0)
        self._stopped = True

    def _fresh(self, now):
        return self.last_drive_ms is not None and now - self.last_drive_ms <= self.failsafe_ms

    def handle(self, pkt, now):
        k = pkt.get("type")
        if k == "D":
            seq = pkt["seq"]
            # after a gamepad reboot the seq restarts; accept anything once the link was silent
            if self._fresh(now) and self.last_seq is not None and not seq_newer(seq, self.last_seq):
                return
            self.last_seq = seq
            self.last_drive_ms = now
            self.throttle = pkt["throttle"]
            self.turn = pkt["turn"]
        elif k == "L":
            self.lights.apply(pkt, now)
        elif k == "R":
            self._start_recoil(pkt["ms"], now)

    def step(self, now):
        """Drive the motors for this loop pass. Returns True while recoil overrides the stick."""
        override = bool(self._recoil_active(now))
        if not self._fresh(now):  # failsafe wins, even during recoil
            if not self._stopped:
                self.motors.stop()
                self._stopped = True
            return override
        if override:
            t, r = self._recoil_command(now)
        else:
            t, r = self.throttle, self.turn
        if self._sonar_gate:
            t = self._sonar_gate(t, self.distance)
        if self._edge_gate:
            t, r = self._edge_gate(t, r, self.line[0], self.line[1])
        self.motors.set_drive(t, r)
        self._stopped = False
        return override


def main():
    from microbit import running_time, sleep
    import radio
    import motors, sonar, edge, lights, recoil, telemetry

    radio.config(group=RADIO_GROUP, channel=RADIO_CHANNEL, length=32, queue=6)
    radio.on()
    snr = sonar.Sonar()
    ctl = Controller(motors.Motors(), lights.Lights(), recoil.start_recoil, recoil.active,
                     recoil.command, sonar.gate, edge.edge_gate)
    tel = telemetry.Telemetry(radio.send)
    last_sonar = 0
    while True:
        now = running_time()
        while True:
            msg = radio.receive()
            if msg is None:
                break
            pkt = decode(msg)
            if pkt:
                ctl.handle(pkt, now)
        if now - last_sonar >= SONAR_PERIOD_MS:
            ctl.distance = snr.read_cm()
            ctl.line = edge.line_state()
            last_sonar = now
        override = ctl.step(now)
        ctl.lights.tick(now)
        tel.maybe_send(now, ctl.distance, ctl.line, override)
        sleep(5)


if __name__ == "__main__":
    main()
