# micro:bit radio packet codec (T05, contract C6) - MicroPython version.
# Same behaviour as server/common/radio_codec.py. No f-strings, no dataclasses, no typing.
# Small enough to paste into each firmware file. decode() never raises; bad input -> None.

MS_MAX = 5000
DIST_MAX = 999
_BTN = {"light": "L", "horn": "H", "shout": "S", "reset": "R"}
_BTN_R = {"L": "light", "H": "horn", "S": "shout", "R": "reset"}
_MODE = {"solid": "S", "flash": "F", "pulse": "P"}
_MODE_R = {"S": "solid", "F": "flash", "P": "pulse"}


def _clamp(v, lo, hi):
    v = int(round(float(v)))
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def _int(s, lo, hi):
    s = s.strip()
    neg = s[:1] == "-"
    d = s[1:] if neg else s
    if not d:
        raise ValueError()
    for c in d:
        if c < "0" or c > "9":
            raise ValueError()
    v = int(s)
    if v < lo or v > hi:
        raise ValueError()
    return v


def encode(m):
    try:
        k = m["kind"]
        if k == "drive":
            out = "D," + str(_clamp(m["throttle"], -100, 100)) + "," + str(_clamp(m["turn"], -100, 100)) \
                + "," + str(int(m.get("seq", 0)) % 256)
        elif k == "button":
            out = "B," + _BTN[m["button"]]
        elif k == "lights":
            c = m["rgb"]
            out = "L," + _MODE[m["mode"]] + "," + str(_clamp(c[0], 0, 255)) + "," + str(_clamp(c[1], 0, 255)) \
                + "," + str(_clamp(c[2], 0, 255)) + "," + str(_clamp(m["ms"], 0, MS_MAX))
        elif k == "recoil":
            out = "R," + str(_clamp(m["ms"], 0, MS_MAX))
        elif k == "rumble":
            out = "V," + str(_clamp(m["ms"], 0, MS_MAX))
        elif k == "telemetry":
            ln = m["line"]
            out = "T," + str(_clamp(m["distance_cm"], 0, DIST_MAX)) + "," + ("1" if ln[0] else "0") + "," \
                + ("1" if ln[1] else "0") + "," + ("1" if m["override"] else "0")
        else:
            return None
    except Exception:
        return None
    if len(out) > 32:
        return None
    return out


def decode(p):
    try:
        if not isinstance(p, str):
            p = str(p, "ascii")
        p = p.strip()
        if not p or len(p) > 32:
            return None
        f = p.split(",")
        t = f[0]
        n = len(f)
        if t == "D" and n == 4:
            return {"kind": "drive", "throttle": _int(f[1], -100, 100), "turn": _int(f[2], -100, 100),
                    "seq": _int(f[3], 0, 255)}
        if t == "B" and n == 2 and f[1] in _BTN_R:
            return {"kind": "button", "button": _BTN_R[f[1]]}
        if t == "L" and n == 6 and f[1] in _MODE_R:
            return {"kind": "lights", "mode": _MODE_R[f[1]],
                    "rgb": [_int(f[2], 0, 255), _int(f[3], 0, 255), _int(f[4], 0, 255)],
                    "ms": _int(f[5], 0, MS_MAX)}
        if t == "R" and n == 2:
            return {"kind": "recoil", "ms": _int(f[1], 0, MS_MAX)}
        if t == "V" and n == 2:
            return {"kind": "rumble", "ms": _int(f[1], 0, MS_MAX)}
        if t == "T" and n == 5:
            return {"kind": "telemetry", "distance_cm": _int(f[1], 0, DIST_MAX),
                    "line": [_int(f[2], 0, 1), _int(f[3], 0, 1)], "override": _int(f[4], 0, 1) == 1}
    except Exception:
        return None
    return None
