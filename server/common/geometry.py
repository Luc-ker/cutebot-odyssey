"""Table geometry helpers (T06, contracts C1/C7).

Table coordinates are normalised `[x, y]` with `0..1` on each axis, origin top-left, `y` down.
Headings are radians, 0 along +x, clockwise positive (because y points down), range (-pi, pi].
"""
from __future__ import annotations

import math
from typing import Sequence

Point = Sequence[float]

_table_cm: tuple[float, float] | None = None


def dist(a: Point, b: Point) -> float:
    """Euclidean distance in normalised table units."""
    return math.hypot(b[0] - a[0], b[1] - a[1])


def wrap_angle(a: float) -> float:
    """Wrap an angle into (-pi, pi]."""
    a = math.fmod(a, 2 * math.pi)
    if a <= -math.pi:
        a += 2 * math.pi
    elif a > math.pi:
        a -= 2 * math.pi
    return a


def angle_to(a: Point, b: Point) -> float:
    """Heading from `a` to `b` in the C1 convention."""
    return math.atan2(b[1] - a[1], b[0] - a[0])


def angle_diff(a: float, b: float) -> float:
    """`a - b`, wrapped into (-pi, pi]."""
    return wrap_angle(a - b)


def in_cone(origin: Point, heading: float, target: Point, half_angle: float, max_dist: float) -> bool:
    """True when `target` is within `max_dist` of `origin` and within `half_angle` radians of `heading`."""
    d = dist(origin, target)
    if d > max_dist:
        return False
    if d == 0:
        return True
    return abs(angle_diff(angle_to(origin, target), heading)) <= half_angle


def _table_size(cfg: dict | None) -> tuple[float, float]:
    global _table_cm
    if cfg is not None:
        return float(cfg["TABLE_W_CM"]), float(cfg["TABLE_H_CM"])
    if _table_cm is None:
        from server.common.config import load_config

        c = load_config()
        _table_cm = (float(c["TABLE_W_CM"]), float(c["TABLE_H_CM"]))
    return _table_cm


def cm_to_units(cm: float, axis: str | int, cfg: dict | None = None) -> float:
    """Convert centimetres along `axis` ("x"/0 or "y"/1) into normalised table units."""
    w, h = _table_size(cfg)
    if axis in ("x", 0):
        return cm / w
    if axis in ("y", 1):
        return cm / h
    raise ValueError(f"axis must be 'x' or 'y', not {axis!r}")


def units_to_cm(units: float, axis: str | int, cfg: dict | None = None) -> float:
    """Inverse of `cm_to_units`."""
    return units * cm_to_units(1.0, axis, cfg) ** -1
