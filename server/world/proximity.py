"""T57 — Danger and friendly proximity events.

Watches ``robot.state`` against ``world.objects`` and publishes ``world.event``:

* ``danger_enter {id, name, role}`` / ``danger_exit {id}`` for threats, radius
  ``DANGER_RADIUS`` + half the object's size;
* ``friendly_enter {id, name, role}`` for friendly objects and for clusters
  (villages, harbours... are friendly places), radius ``FRIENDLY_RADIUS`` + half size.

Hysteresis: inside once closer than the radius, outside again only beyond
1.2× the radius. An enter is announced at most once per object per 3 s; an
exit is only sent for an announced enter (also when the threat vanishes or
stops being a threat). Nothing happens while ``robot.state.seen`` is false.
"""

from __future__ import annotations

import math
import time

DEFAULT_DANGER_RADIUS = 0.12
DEFAULT_FRIENDLY_RADIUS = 0.10
EXIT_FACTOR = 1.2
ENTER_COOLDOWN_S = 3.0


def _half_size(o) -> float:
    size = o.get("size") or [0, 0]
    return max(size[:2] or [0]) / 2


class Proximity:
    def __init__(self, config: dict | None = None):
        config = config or {}
        self.danger_r = float(config.get("DANGER_RADIUS", DEFAULT_DANGER_RADIUS))
        self.friendly_r = float(config.get("FRIENDLY_RADIUS", DEFAULT_FRIENDLY_RADIUS))
        self.reset()

    def reset(self):
        self.inside: dict[tuple, bool] = {}     # (kind, id) -> announced?
        self.last_enter: dict[tuple, float] = {}

    def _targets(self, world_objects: dict):
        for o in world_objects.get("objects") or []:
            if o.get("behaviour") == "threat":
                yield "danger", o, self.danger_r + _half_size(o)
            elif o.get("behaviour") == "friendly":
                yield "friendly", o, self.friendly_r + _half_size(o)
        for c in world_objects.get("clusters") or []:
            yield "friendly", c, self.friendly_r + _half_size(c)

    def update(self, robot: dict, world_objects: dict | None, now: float) -> list[dict]:
        if not robot or not robot.get("seen") or robot.get("pos") is None:
            return []
        events = []
        rx, ry = robot["pos"][:2]
        present = set()
        for kind, o, radius in self._targets(world_objects or {}):
            key = (kind, o["id"])
            present.add(key)
            d = math.hypot(o["pos"][0] - rx, o["pos"][1] - ry)
            if key not in self.inside:
                if d < radius:
                    announce = now - self.last_enter.get(key, -math.inf) >= ENTER_COOLDOWN_S
                    self.inside[key] = announce
                    if announce:
                        self.last_enter[key] = now
                        events.append({"kind": f"{kind}_enter", "id": o["id"],
                                       "name": o.get("name"), "role": o.get("role")})
            elif d > radius * EXIT_FACTOR:
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
