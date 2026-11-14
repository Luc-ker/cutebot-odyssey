"""T56 — Facing-object detection.

Which object is directly in front of the robot, for the HUD label, the video
prompt and the Shout button.

Contract (C7)::

    facing(robot_state, objects, clusters=None) -> int | None

Candidates are inside a cone of ``FACING_HALF_ANGLE_DEG`` and ``FACING_MAX_DIST``
(table units) around the robot heading. Cost = distance × (1 + angle / half_angle),
lowest wins, so the nearest wins unless it is far off-axis.

Hysteresis: the current target is kept while it is still in the cone, unless
another candidate's cost is at least 20 % lower.

Clusters (T52) count as targets too. **Choice:** cluster ids are plain ints from
``100001`` upwards (T52's ``CLUSTER_ID_BASE``), so the result stays a single int
that fits ``robot.state.facing_id: int | None``; consumers look the id up in
``world.objects.clusters`` when it is ``>= 100000``.

``FacingTracker`` holds the hysteresis state; ``facing()`` uses a shared default.
"""

from __future__ import annotations

import math

DEFAULT_HALF_ANGLE_DEG = 25.0
DEFAULT_MAX_DIST = 0.35
SWITCH_MARGIN = 0.2

try:  # T06
    from server.common.geometry import angle_diff, angle_to, dist
except ImportError:  # until T06 lands
    def dist(a, b):
        return math.hypot(b[0] - a[0], b[1] - a[1])

    def angle_to(a, b):
        return math.atan2(b[1] - a[1], b[0] - a[0])

    def angle_diff(a, b):
        d = (a - b) % (2 * math.pi)
        return d - 2 * math.pi if d > math.pi else d


def _get(o, key, default=None):
    return o.get(key, default) if isinstance(o, dict) else getattr(o, key, default)


class FacingTracker:
    def __init__(self, config: dict | None = None):
        config = config or {}
        self.half_angle = math.radians(float(config.get("FACING_HALF_ANGLE_DEG", DEFAULT_HALF_ANGLE_DEG)))
        self.max_dist = float(config.get("FACING_MAX_DIST", DEFAULT_MAX_DIST))
        self.current: int | None = None

    def reset(self):
        self.current = None

    def _cost(self, pos, heading, target) -> float | None:
        d = dist(pos, target)
        if d > self.max_dist:
            return None
        if d < 1e-9:
            return 0.0
        a = abs(angle_diff(angle_to(pos, target), heading))
        if a > self.half_angle:
            return None
        return d * (1 + a / self.half_angle)

    def update(self, robot, objects, clusters=None) -> int | None:
        pos = _get(robot or {}, "pos")
        heading = _get(robot or {}, "heading")
        if pos is None or heading is None:
            self.current = None
            return None
        costs: dict[int, float] = {}
        for t in list(objects or []) + list(clusters or []):
            tpos, tid = _get(t, "pos"), _get(t, "id")
            if tpos is None or tid is None:
                continue
            c = self._cost(pos, heading, tpos)
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


def facing(robot, objects, clusters=None, tracker: FacingTracker | None = None) -> int | None:
    return (tracker or _default).update(robot, objects, clusters)
