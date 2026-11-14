import importlib.util
import os

_spec = importlib.util.spec_from_file_location("bridge_main", os.path.join(os.path.dirname(__file__), "main.py"))
bm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bm)


def make():
    ser, rad = [], []
    return bm.Bridge(ser.append, rad.append), ser, rad


def test_serial_in_goes_to_radio_unchanged():
    b, ser, rad = make()
    b.from_serial("L,F,255,0,0,100\n")
    assert rad == ["L,F,255,0,0,100"]


def test_invalid_serial_lines_are_not_sent():
    b, _, rad = make()
    for bad in ("", "hello", "L,X,1,2,3,4", "R,abc", "D,1,2"):
        assert not b.from_serial(bad)
    assert rad == []


def test_three_identical_buttons_become_one_line():
    b, ser, _ = make()
    for t in (0, 20, 40):
        b.from_radio("B,H", t)
    assert ser == ["B,H\n"]
    b.from_radio("B,H", 400)         # a genuinely new press later
    assert len(ser) == 2


def test_telemetry_forwarded_and_drive_dropped():
    b, ser, _ = make()
    b.from_radio("T,12,0,1,0", 0)
    b.from_radio("D,10,0,1", 1)
    assert ser == ["T,12,0,1,0\n"]
