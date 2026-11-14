"""Geometry helpers (T06, contracts C1/C7).

View coordinates are normalised `[x, y]` in the robot camera's frame, `0..1` on each axis, origin top-left,
`y` down. Angles are radians; `angle_to` follows the same y-down convention (clockwise positive).
"""
from __future__ import annotations

import math
from typing import Sequence

Point = Sequence[float]

def dist(a: Point, b: Point) -> float:
    """Euclidean distance in normalised view units."""
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


def bearing(x: float, hfov_deg: float) -> float:
    """Angle (radians) from straight ahead to a point at view x (0..1). Negative = left, positive = right.

    Uses a pinhole camera with horizontal field of view `hfov_deg`, so the edges of the frame are at
    ±hfov/2 and the centre is 0.
    """
    half = math.radians(hfov_deg) / 2
    return math.atan((2 * float(x) - 1) * math.tan(half))


def view_size(size: Sequence[float] | None) -> float:
    """How much of the view an object takes up: the larger of its width and height (0..1)."""
    if not size:
        return 0.0
    return max(float(v) for v in size[:2])
