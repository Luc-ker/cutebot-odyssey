"""T56 — Facing-object detection.

Which object is directly in front of the robot, for the HUD label, the video
prompt and the Shout button.

Contract (C7)::

    facing(objects, clusters=None) -> int | None

The camera looks where the robot looks, so "in front" means near the middle of
the view. Candidates are objects in view (``visible`` not false) that

* are within ``FACING_HALF_ANGLE_DEG`` of straight ahead (the angle comes from the
  object's x in the view and the camera's ``CAMERA_HFOV_DEG``), and
* take up at least ``FACING_MIN_SIZE`` of the view (smaller ones are far away).

Cost = (1 + angle / half_angle) / size, lowest wins: the biggest (nearest) wins
unless it is far off-centre.

Hysteresis: the current target is kept while it is still a candidate, unless
another candidate's cost is at least 20 % lower.

Clusters (T52) count as targets too, with their own ``size`` if they have one.
**Choice:** cluster ids are plain ints from ``100001`` upwards (T52's
``CLUSTER_ID_BASE``), so the result stays a single int that fits
``robot.state.facing_id: int | None``; consumers look the id up in
``world.objects.clusters`` when it is ``>= 100000``.

``FacingTracker`` holds the hysteresis state; ``facing()`` uses a shared default.
"""

from __future__ import annotations

import math

from server.common.geometry import bearing, view_size

DEFAULT_HALF_ANGLE_DEG = 15.0
DEFAULT_MIN_SIZE = 0.08
DEFAULT_HFOV_DEG = 65.0
SWITCH_MARGIN = 0.2


def _get(o, key, default=None):
    return o.get(key, default) if isinstance(o, dict) else getattr(o, key, default)


class FacingTracker:
    def __init__(self, config: dict | None = None):
        config = config or {}
        self.half_angle = math.radians(float(config.get("FACING_HALF_ANGLE_DEG", DEFAULT_HALF_ANGLE_DEG)))
        self.min_size = float(config.get("FACING_MIN_SIZE", DEFAULT_MIN_SIZE))
        self.hfov_deg = float(config.get("CAMERA_HFOV_DEG", DEFAULT_HFOV_DEG))
        self.current: int | None = None

    def reset(self):
        self.current = None

    def cost(self, target) -> float | None:
        if _get(target, "visible", True) is False:
            return None
        pos = _get(target, "pos")
        if pos is None:
            return None
        size = view_size(_get(target, "size")) or self.min_size
        if size < self.min_size:
            return None
        a = abs(bearing(pos[0], self.hfov_deg))
        if a > self.half_angle:
            return None
        return (1 + a / self.half_angle) / size

    def update(self, objects, clusters=None) -> int | None:
        costs: dict[int, float] = {}
        for t in list(objects or []) + list(clusters or []):
            tid = _get(t, "id")
            if tid is None:
                continue
            c = self.cost(t)
            if c is not None:
                costs[tid] = c
        if not costs:
            self.current = None
            return None
        best = min(costs, key=costs.get)
        if self.current in costs and best != self.current:
            if costs[best] > costs[self.current] * (1 - SWITCH_MARGIN):
                best = self.current
        self.current = best
        return best


_default = FacingTracker()


def facing(objects, clusters=None, tracker: FacingTracker | None = None) -> int | None:
    return (tracker or _default).update(objects, clusters)
