import importlib.util
import re
from pathlib import Path

import pytest

from server.common import radio_codec

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("fw_codec", REPO / "firmware" / "common" / "codec.py")
fw_codec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fw_codec)

CODECS = [pytest.param(radio_codec, id="laptop"), pytest.param(fw_codec, id="firmware")]

EXAMPLES = [
    ({"kind": "drive", "throttle": -100, "turn": 37, "seq": 255}, "D,-100,37,255"),
    ({"kind": "button", "button": "shout"}, "B,S"),
    ({"kind": "lights", "mode": "pulse", "rgb": [255, 128, 0], "ms": 5000}, "L,P,255,128,0,5000"),
    ({"kind": "recoil", "ms": 600}, "R,600"),
    ({"kind": "rumble", "ms": 250}, "V,250"),
    ({"kind": "telemetry", "distance_cm": 12, "line": [0, 1], "override": True}, "T,12,0,1,1"),
]

WORST_CASE = [
    {"kind": "drive", "throttle": -100, "turn": -100, "seq": 255},
    {"kind": "lights", "mode": "flash", "rgb": [255, 255, 255], "ms": 5000},
    {"kind": "telemetry", "distance_cm": 999, "line": [1, 1], "override": True},
    {"kind": "recoil", "ms": 5000},
]

BAD = ["", "D,abc,1,2", "D,1,2", "D,1,2,3,4", "D,101,0,0", "D,1.5,0,0", "D,,0,0", "X,1", "B,Q", "B",
       "L,Z,1,2,3,4", "L,S,256,0,0,10", "R,-1", "R,5001", "V,", "T,10,2,0,0", "T,10,0,0", "D, 1 ,2,3x",
       "D,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15", None, 42, b"\xff\xfe", "B,L,extra"]


@pytest.mark.parametrize("codec", CODECS)
@pytest.mark.parametrize("msg, wire", EXAMPLES, ids=[e[1] for e in EXAMPLES])
def test_round_trip(codec, msg, wire):
    assert codec.encode(msg) == wire
    assert codec.decode(codec.encode(msg)) == msg


@pytest.mark.parametrize("codec", CODECS)
def test_packets_fit_32_bytes(codec):
    for msg in WORST_CASE + [m for m, _ in EXAMPLES]:
        out = codec.encode(msg)
        assert out is not None and len(out.encode("ascii")) <= 32, out


@pytest.mark.parametrize("codec", CODECS)
@pytest.mark.parametrize("bad", BAD, ids=repr)
def test_bad_input_returns_none(codec, bad):
    assert codec.decode(bad) is None


@pytest.mark.parametrize("codec", CODECS)
def test_encode_clamps(codec):
    assert codec.encode({"kind": "drive", "throttle": 250, "turn": -300, "seq": 256}) == "D,100,-100,0"
    assert codec.encode({"kind": "lights", "mode": "solid", "rgb": [-5, 300, 12.6], "ms": 99999}) == "L,S,0,255,13,5000"
    assert codec.encode({"kind": "recoil", "ms": -10}) == "R,0"
    assert codec.encode({"kind": "telemetry", "distance_cm": 4000, "line": [True, False], "override": 0}) == "T,999,1,0,0"


@pytest.mark.parametrize("codec", CODECS)
def test_encode_bad_dict_returns_none(codec):
    assert codec.encode({"kind": "warp"}) is None
    assert codec.encode({"kind": "button", "button": "jump"}) is None
    assert codec.encode({"kind": "drive", "throttle": "fast", "turn": 0}) is None
    assert codec.encode({}) is None


@pytest.mark.parametrize("codec", CODECS)
def test_decode_accepts_serial_newline_and_bytes(codec):
    assert codec.decode("B,H\n") == {"kind": "button", "button": "horn"}
    assert codec.decode(b"R,100\r\n") == {"kind": "recoil", "ms": 100}


def test_firmware_avoids_unsupported_syntax():
    lines = (REPO / "firmware" / "common" / "codec.py").read_text().splitlines()
    src = "\n".join(l for l in lines if not l.lstrip().startswith("#"))
    assert not re.search(r"\bf[\"']", src), "f-strings are not safe on every MicroPython build"
    assert "dataclass" not in src and "typing" not in src
