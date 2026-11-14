import time
import lights


def make():
    out = []
    return lights.Lights(lambda r, g, b: out.append((r, g, b))), out


def test_flash_over_base():
    l, out = make()
    l.apply({"mode": "S", "rgb": [0, 0, 255], "ms": 0}, 0)
    l.apply({"mode": "F", "rgb": [255, 0, 0], "ms": 100}, 0)
    assert out[-1] == (255, 0, 0)
    l.tick(50)
    assert out[-1] == (255, 0, 0)
    l.tick(150)
    assert out[-1] == (0, 0, 255)


def test_pulse_peaks_in_the_middle_and_returns():
    l, out = make()
    l.apply({"mode": "S", "rgb": [0, 0, 0], "ms": 0}, 0)
    l.apply({"mode": "P", "rgb": [200, 0, 0], "ms": 1000}, 0)
    l.tick(500)
    assert out[-1] == (200, 0, 0)
    l.tick(1100)
    assert out[-1] == (0, 0, 0)


def test_tick_is_fast_and_only_writes_on_change():
    l, out = make()
    l.apply({"mode": "S", "rgb": [1, 2, 3], "ms": 0}, 0)
    n = len(out)
    t0 = time.perf_counter()
    for i in range(1000):
        l.tick(i)
    assert (time.perf_counter() - t0) / 1000 < 0.002
    assert len(out) == n
