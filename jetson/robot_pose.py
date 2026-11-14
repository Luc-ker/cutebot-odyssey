"""Robot pose smoothing and freeze on loss (T42, contracts C1/C8).

    pose = RobotPose(calib)
    pose.update(find_robot(frame), ts) -> {"pos": [x, y] | None, "heading": rad | None, "seen": bool}

- The pixel measurement is converted to table coordinates; heading is the angle between the transformed centre
  and a point a little ahead of it, so perspective is accounted for.
- Position uses exponential smoothing, heading uses circular smoothing (works across the ±π wrap).
- A measurement further away than the robot could physically travel since the last accepted one is rejected.
  If several consecutive measurements agree on a new spot, the filter re-locks there (the robot was picked up).
- `None` keeps the last pose with `seen: false`, indefinitely (the map freezes the marker rather than jumping).
"""
from __future__ import annotations

import math

from server.common.geometry import wrap_angle

ALPHA_POS = 0.5             # weight of a new measurement
ALPHA_HEADING = 0.5
MAX_SPEED = 1.0             # table units per second (Cutebot is ~0.5 m/s, table ~1.2 m wide) with headroom
JUMP_SLACK = 0.05           # table units allowed on top of MAX_SPEED * dt (detection noise)
RELOCK_FRAMES = 4           # consecutive consistent "jumps" that are accepted as a real relocation
RELOCK_RADIUS = 0.05
HEADING_PROBE_PX = 20.0


class RobotPose:
    def __init__(self, calib, alpha_pos: float = ALPHA_POS, alpha_heading: float = ALPHA_HEADING,
                 max_speed: float = MAX_SPEED):
        self.calib = calib
        self.alpha_pos = alpha_pos
        self.alpha_heading = alpha_heading
        self.max_speed = max_speed
        self.pos: list[float] | None = None
        self.heading: float | None = None
        self.seen = False
        self.last_accept_ts: float | None = None
        self.last_seen_ts: float | None = None
        self._candidates: list[list[float]] = []

    def reset(self) -> None:
        self.__init__(self.calib, self.alpha_pos, self.alpha_heading, self.max_speed)

    def _measure(self, m: dict) -> tuple[list[float], float]:
        u, v = m["px"]
        h = float(m["heading"])
        pos = self.calib.to_table([u, v], clamp=False)
        ahead = self.calib.to_table([u + HEADING_PROBE_PX * math.cos(h), v + HEADING_PROBE_PX * math.sin(h)],
                                    clamp=False)
        heading = math.atan2(ahead[1] - pos[1], ahead[0] - pos[0])
        clamped = [min(max(pos[0], 0.0), 1.0), min(max(pos[1], 0.0), 1.0)]
        return clamped, heading

    def _state(self) -> dict:
        return {"pos": None if self.pos is None else list(self.pos), "heading": self.heading, "seen": self.seen}

    def update(self, measurement: dict | None, ts: float) -> dict:
        if measurement is None:
            self.seen = False
            return self._state()
        try:
            pos, heading = self._measure(measurement)
        except (KeyError, TypeError, ValueError):
            self.seen = False
            return self._state()

        if self.pos is None:
            self._accept(pos, heading, ts, reset=True)
            return self._state()

        dt = max(0.0, ts - self.last_accept_ts) if self.last_accept_ts is not None else 0.0
        jump = math.dist(pos, self.pos)
        if jump > self.max_speed * dt + JUMP_SLACK:
            # Outlier, unless the last few outliers agree with each other (robot was moved by hand).
            self._candidates = [c for c in self._candidates if math.dist(c, pos) <= RELOCK_RADIUS]
            self._candidates.append(pos)
            if len(self._candidates) >= RELOCK_FRAMES:
                self._accept(pos, heading, ts, reset=True)
            return self._state()  # a rejected frame leaves `seen` as it was

        self._accept(pos, heading, ts, reset=False)
        return self._state()

    def _accept(self, pos: list[float], heading: float, ts: float, reset: bool) -> None:
        if reset or self.pos is None or self.heading is None:
            self.pos, self.heading = list(pos), wrap_angle(heading)
        else:
            a = self.alpha_pos
            self.pos = [self.pos[0] + a * (pos[0] - self.pos[0]), self.pos[1] + a * (pos[1] - self.pos[1])]
            # Circular smoothing: step along the shortest arc.
            self.heading = wrap_angle(self.heading + self.alpha_heading * wrap_angle(heading - self.heading))
        self._candidates.clear()
        self.seen = True
        self.last_accept_ts = ts
        self.last_seen_ts = ts
