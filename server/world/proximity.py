"""T57 — Danger and friendly proximity events.

Watches ``robot.state`` against ``world.objects`` and publishes ``world.event``:

* ``danger_enter {id, name, role}`` / ``danger_exit {id}`` for threats;
* ``friendly_enter {id, name, role}`` for friendly objects and for clusters
  (villages, harbours... are friendly places).

There is no map, so "near" is judged from the robot's own view. An object is near when it is in view,
**ahead** (its box reaches into the middle band of the view) and **close**, meaning either

* it is big in the view: ``size`` (the larger of its width and height) ≥ ``DANGER_SIZE`` for threats or
  ``FRIENDLY_SIZE`` for friendly objects, or
* it is the object the robot is facing and the ultrasonic sensor reads ≤ ``NEAR_CM``.

Hysteresis: once near, an object only counts as left when it is out of view, no longer ahead, or less than
``1 / 1.2`` as close. An enter is announced at most once per object per 3 s; an exit is only sent for an
announced enter (also when the threat vanishes or stops being a threat).
"""

from __future__ import annotations

import math
import time

from server.common.geometry import view_size

DEFAULT_DANGER_SIZE = 0.35
DEFAULT_FRIENDLY_SIZE = 0.3
DEFAULT_NEAR_CM = 20.0
CENTRE_BAND = 0.2          # half-width of the middle band of the view, in view units
EXIT_FACTOR = 1.2
ENTER_COOLDOWN_S = 3.0


def _ahead(o) -> bool:
    pos = o.get("pos")
    if pos is None:
        return False
    half_w = (o.get("size") or [0, 0])[0] / 2
    return abs(pos[0] - 0.5) - half_w <= CENTRE_BAND


class Proximity:
    def __init__(self, config: dict | None = None):
        config = config or {}
        self.danger_size = float(config.get("DANGER_SIZE", DEFAULT_DANGER_SIZE))
        self.friendly_size = float(config.get("FRIENDLY_SIZE", DEFAULT_FRIENDLY_SIZE))
        self.near_cm = float(config.get("NEAR_CM", DEFAULT_NEAR_CM))
        self.reset()

    def reset(self):
        self.inside: dict[tuple, bool] = {}     # (kind, id) -> announced?
        self.last_enter: dict[tuple, float] = {}

    def _targets(self, world_objects: dict):
        for o in world_objects.get("objects") or []:
            if o.get("behaviour") == "threat":
                yield "danger", o, self.danger_size
            elif o.get("behaviour") == "friendly":
                yield "friendly", o, self.friendly_size
        for c in world_objects.get("clusters") or []:
            yield "friendly", c, self.friendly_size

    def closeness(self, o, threshold: float, robot: dict) -> float:
        """≥ 1 means close enough to enter; 0 means out of view or not ahead."""
        if o.get("visible") is False or not _ahead(o):
            return 0.0
        c = view_size(o.get("size")) / threshold
        d = robot.get("distance_cm")
        if robot.get("facing_id") == o.get("id") and isinstance(d, (int, float)):
            c = max(c, self.near_cm / max(float(d), 1e-6))
        return c

    def update(self, robot: dict, world_objects: dict | None, now: float) -> list[dict]:
        robot = robot or {}
        events = []
        present = set()
        for kind, o, threshold in self._targets(world_objects or {}):
            if o.get("id") is None:
                continue
            key = (kind, o["id"])
            present.add(key)
            c = self.closeness(o, threshold, robot)
            if key not in self.inside:
                if c >= 1.0:
                    announce = now - self.last_enter.get(key, -math.inf) >= ENTER_COOLDOWN_S
                    self.inside[key] = announce
                    if announce:
                        self.last_enter[key] = now
                        events.append({"kind": f"{kind}_enter", "id": o["id"],
                                       "name": o.get("name"), "role": o.get("role")})
            elif c < 1.0 / EXIT_FACTOR:
                events += self._leave(key)
        for key in [k for k in self.inside if k not in present]:
            events += self._leave(key)
        return events

    def _leave(self, key) -> list[dict]:
        announced = self.inside.pop(key)
        kind, obj_id = key
        if kind == "danger" and announced:
            return [{"kind": "danger_exit", "id": obj_id}]
        return []


async def run(hub, config, *, clock=time.time):
    prox = Proximity(config)
    latest: dict = {"objects": None}

    async def on_objects(env):
        latest["objects"] = env.get("data") or {}

    async def on_robot(env):
        for ev in prox.update(env.get("data") or {}, latest["objects"], clock()):
            await hub.pub("world.event", ev)

    async def on_reset(_env):
        prox.reset()
        latest["objects"] = None

    hub.sub("world.objects", on_objects)
    hub.sub("robot.state", on_robot)
    hub.sub("system.reset", on_reset)
    return prox
