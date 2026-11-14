"""T60 — Physical-block detection.

The robot is blocked when ``robot.state.distance_cm`` < ``SAFETY_STOP_CM + 2``
for more than 1 s while that distance has not changed by more than 1.5 cm (it is
held at the obstacle, not driving past it). There is no position on the table, so
the steady sensor reading is what says the robot isn't moving.
Then ``world.event blocked {obstacle}`` is published, once per blocking episode
and at most every 6 s. The obstacle word is the facing object's (or cluster's)
name if there is one, else a word for the world's setting.
"""

from __future__ import annotations

import time

DEFAULT_SAFETY_STOP_CM = 8.0
HOLD_S = 1.0
STILL_CM = 1.5
COOLDOWN_S = 6.0

# First matching keyword in the setting/name wins.
OBSTACLE_WORDS = [
    (("sea", "ocean", "coast", "island"), "reef"),
    (("wasteland", "volcan", "lava"), "lava wall"),
    (("snow", "ice", "frost", "winter"), "ice cliff"),
    (("jungle", "rainforest"), "wall of vines"),
    (("city", "neon"), "barricade"),
    (("space", "station"), "bulkhead"),
    (("court", "royal", "palace"), "marble wall"),
]
DEFAULT_WORD = "wall"


def obstacle_word(world: dict | None) -> str:
    world = world or {}
    info = world.get("world", world) if isinstance(world.get("world"), dict) else world
    text = f"{info.get('setting', '')} {info.get('name', '')}".lower()
    for keys, word in OBSTACLE_WORDS:
        if any(k in text for k in keys):
            return word
    return DEFAULT_WORD


class BlockedDetector:
    def __init__(self, config: dict | None = None):
        config = config or {}
        self.limit_cm = float(config.get("SAFETY_STOP_CM", DEFAULT_SAFETY_STOP_CM)) + 2
        self.reset()

    def reset(self):
        self.since: float | None = None
        self.anchor = None
        self.fired = False
        self.last_fired: float | None = None

    def update(self, robot: dict, now: float, world: dict | None = None,
               names: dict | None = None) -> dict | None:
        """``names`` maps target id → name (objects and clusters from world.objects)."""
        d = (robot or {}).get("distance_cm")
        if d is None or d >= self.limit_cm:
            self.since, self.anchor, self.fired = None, None, False
            return None
        if self.since is None or abs(d - self.anchor) > STILL_CM:
            self.since, self.anchor, self.fired = now, d, False
            return None
        if self.fired or now - self.since <= HOLD_S:
            return None
        if self.last_fired is not None and now - self.last_fired < COOLDOWN_S:
            return None
        self.fired, self.last_fired = True, now
        facing_name = (names or {}).get(robot.get("facing_id"))
        return {"kind": "blocked", "obstacle": facing_name or obstacle_word(world)}


async def run(hub, config, *, clock=time.time):
    det = BlockedDetector(config)
    ctx = {"world": None, "names": {}}

    async def on_world(env):
        ctx["world"] = (env.get("data") or {}).get("world")

    async def on_objects(env):
        data = env.get("data") or {}
        ctx["names"] = {o["id"]: o.get("name") for o in
                        (data.get("objects") or []) + (data.get("clusters") or []) if o.get("name")}

    async def on_robot(env):
        ev = det.update(env.get("data") or {}, clock(), ctx["world"], ctx["names"])
        if ev:
            await hub.pub("world.event", ev)

    async def on_reset(_env):
        det.reset()

    hub.sub("world.current", on_world)
    hub.sub("world.objects", on_objects)
    hub.sub("robot.state", on_robot)
    hub.sub("system.reset", on_reset)
    return det
