import importlib.util
import os
import motors  # noqa: F401  (ensures this dir is importable)
import recoil
import sonar

_spec = importlib.util.spec_from_file_location("cutebot_main", os.path.join(os.path.dirname(__file__), "main.py"))
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)


class FakeMotors:
    def __init__(self):
        self.calls = []

    def set_drive(self, t, r):
        self.calls.append(("drive", t, r))

    def stop(self):
        self.calls.append(("stop",))


class FakeLights:
    def __init__(self):
        self.applied = []

    def apply(self, cmd, now):
        self.applied.append(cmd)


def make(**kw):
    recoil.reset()
    m, l = FakeMotors(), FakeLights()
    c = cm.Controller(m, l, recoil.start_recoil, recoil.active, recoil.command, **kw)
    return c, m, l


def D(t, r, s):
    return {"type": "D", "throttle": t, "turn": r, "seq": s}


def test_failsafe_stops_after_silence():
    c, m, _ = make()
    c.handle(D(80, 0, 1), 0)
    c.step(0)
    assert m.calls[-1] == ("drive", 80, 0)
    c.step(400)
    assert m.calls[-1] == ("stop",)


def test_out_of_order_seq_ignored_and_wrap_ok():
    c, m, _ = make()
    c.handle(D(50, 0, 5), 0)
    c.handle(D(99, 0, 3), 10)          # older -> ignored
    c.step(10)
    assert m.calls[-1] == ("drive", 50, 0)
    c.handle(D(10, 0, 100), 15)
    c.handle(D(11, 0, 200), 16)
    c.handle(D(12, 0, 250), 17)
    c.handle(D(20, 0, 2), 30)          # wrapped, newer
    c.step(30)
    assert m.calls[-1] == ("drive", 20, 0)


def test_seq_restart_after_link_loss_is_accepted():
    c, m, _ = make()
    c.handle(D(50, 0, 200), 0)
    c.handle(D(30, 0, 1), 1000)        # gamepad rebooted, link was silent
    c.step(1000)
    assert m.calls[-1] == ("drive", 30, 0)


def test_recoil_overrides_stick_and_reports_override():
    c, m, _ = make()
    c.handle(D(100, 0, 1), 0)
    c.handle({"type": "R", "ms": 700}, 0)
    assert c.step(100) is True
    assert m.calls[-1][1] < 0          # reversing although stick is forward
    c.handle(D(100, 0, 2), 800)
    assert c.step(800) is False
    assert m.calls[-1] == ("drive", 100, 0)


def test_lights_dispatch_and_sonar_gate():
    c, m, l = make(sonar_gate=sonar.gate)
    c.handle({"type": "L", "mode": "F", "rgb": [255, 0, 0], "ms": 100}, 0)
    assert l.applied and l.applied[0]["mode"] == "F"
    c.distance = 4
    c.handle(D(80, 10, 1), 0)
    c.step(0)
    assert m.calls[-1] == ("drive", 0, 10)


def test_fallback_decoder():
    assert cm.decode("D,50,-20,7") == {"type": "D", "throttle": 50, "turn": -20, "seq": 7}
    assert cm.decode("D,abc,1,2") is None
    assert cm.decode("") is None
