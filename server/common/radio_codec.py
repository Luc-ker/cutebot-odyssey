"""micro:bit radio / serial packet codec (T05, contract C6).

Packets are ASCII, comma-separated, at most 32 bytes. Dict forms use `kind`, matching `robot.cmd` (C3):

    {"kind": "drive", "throttle": -100..100, "turn": -100..100, "seq": 0..255}   <-> D,<throttle>,<turn>,<seq>
    {"kind": "button", "button": "light"|"horn"|"shout"|"reset"}                 <-> B,<L|H|S|R>
    {"kind": "lights", "mode": "solid"|"flash"|"pulse", "rgb": [r,g,b], "ms": n}  <-> L,<S|F|P>,<r>,<g>,<b>,<ms>
    {"kind": "recoil", "ms": n}                                                  <-> R,<ms>
    {"kind": "rumble", "ms": n}                                                  <-> V,<ms>
    {"kind": "telemetry", "distance_cm": n, "line": [l, r], "override": bool}    <-> T,<dist_cm>,<lineL>,<lineR>,<override>

`encode` clamps numbers into range (throttle/turn -100..100, colours 0..255, ms 0..5000, seq wraps 0..255,
distance 0..999) and returns None for a dict it cannot encode. `decode` never raises: anything malformed or
out of range returns None. Keep in step with `firmware/common/codec.py`.
"""
from __future__ import annotations

MAX_LEN = 32
MS_MAX = 5000
DIST_MAX = 999

BUTTONS = {"light": "L", "horn": "H", "shout": "S", "reset": "R"}
MODES = {"solid": "S", "flash": "F", "pulse": "P"}
_BUTTONS_REV = {v: k for k, v in BUTTONS.items()}
_MODES_REV = {v: k for k, v in MODES.items()}


def _clamp(v, lo, hi) -> int:
    v = int(round(float(v)))
    return lo if v < lo else hi if v > hi else v


def _int(s: str, lo: int, hi: int) -> int:
    """Strict int parse; raises ValueError when not a plain integer in range."""
    s = s.strip()
    if not s or not (s.isdigit() or (s[0] == "-" and s[1:].isdigit())):
        raise ValueError(s)
    v = int(s)
    if v < lo or v > hi:
        raise ValueError(s)
    return v


def encode(msg: dict) -> str | None:
    """Encode a packet dict to its ASCII form (no newline). Returns None if `msg` is not encodable."""
    try:
        kind = msg["kind"]
        if kind == "drive":
            out = "D,%d,%d,%d" % (_clamp(msg["throttle"], -100, 100), _clamp(msg["turn"], -100, 100),
                                  int(msg.get("seq", 0)) % 256)
        elif kind == "button":
            out = "B," + BUTTONS[msg["button"]]
        elif kind == "lights":
            r, g, b = msg["rgb"]
            out = "L,%s,%d,%d,%d,%d" % (MODES[msg["mode"]], _clamp(r, 0, 255), _clamp(g, 0, 255),
                                        _clamp(b, 0, 255), _clamp(msg["ms"], 0, MS_MAX))
        elif kind == "recoil":
            out = "R,%d" % _clamp(msg["ms"], 0, MS_MAX)
        elif kind == "rumble":
            out = "V,%d" % _clamp(msg["ms"], 0, MS_MAX)
        elif kind == "telemetry":
            l, r = msg["line"]
            out = "T,%d,%d,%d,%d" % (_clamp(msg["distance_cm"], 0, DIST_MAX), 1 if l else 0, 1 if r else 0,
                                     1 if msg["override"] else 0)
        else:
            return None
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    return out if len(out) <= MAX_LEN else None


def decode(packet) -> dict | None:
    """Decode one packet (a trailing newline is fine). Returns None for anything malformed."""
    try:
        if isinstance(packet, (bytes, bytearray)):
            packet = packet.decode("ascii")
        if not isinstance(packet, str):
            return None
        packet = packet.strip()
        if not packet or len(packet) > MAX_LEN:
            return None
        f = packet.split(",")
        t, n = f[0], len(f)
        if t == "D" and n == 4:
            return {"kind": "drive", "throttle": _int(f[1], -100, 100), "turn": _int(f[2], -100, 100),
                    "seq": _int(f[3], 0, 255)}
        if t == "B" and n == 2 and f[1] in _BUTTONS_REV:
            return {"kind": "button", "button": _BUTTONS_REV[f[1]]}
        if t == "L" and n == 6 and f[1] in _MODES_REV:
            return {"kind": "lights", "mode": _MODES_REV[f[1]],
                    "rgb": [_int(f[2], 0, 255), _int(f[3], 0, 255), _int(f[4], 0, 255)],
                    "ms": _int(f[5], 0, MS_MAX)}
        if t == "R" and n == 2:
            return {"kind": "recoil", "ms": _int(f[1], 0, MS_MAX)}
        if t == "V" and n == 2:
            return {"kind": "rumble", "ms": _int(f[1], 0, MS_MAX)}
        if t == "T" and n == 5:
            return {"kind": "telemetry", "distance_cm": _int(f[1], 0, DIST_MAX),
                    "line": [_int(f[2], 0, 1), _int(f[3], 0, 1)], "override": _int(f[4], 0, 1) == 1}
    except (ValueError, UnicodeDecodeError):
        return None
    return None
