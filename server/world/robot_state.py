"""T55 — Robot state aggregator.

Merges what the robot's sensors report (``robot.telemetry``) with which object
it is facing in its camera view (T56), and publishes ``robot.state`` at 10 Hz::

    {distance_cm, override, facing_id}

The camera rides on the robot, so there is no position or heading on the table:
everything is relative to what the robot sees.

Telemetry older than 1 s is stale: ``distance_cm`` becomes ``null`` and
``override`` false. Facing targets come from the latest ``world.objects``
(objects and clusters), or from ``vision.state`` objects until one arrives.
"""

from __future__ import annotations

import asyncio
import time

PUBLISH_HZ = 10.0
TELEMETRY_STALE_S = 1.0


def _default_facing(config):
    try:
        from server.world.facing import FacingTracker  # T56
    except ImportError:
        return lambda objects, clusters=None: None
    return FacingTracker(config).update


class RobotStateAggregator:
    def __init__(self, config: dict | None = None, facing_fn=None):
        self.config = config or {}
        self.facing_fn = facing_fn or _default_facing(self.config)
        self.reset()

    def reset(self):
        self.telemetry: dict | None = None
        self.telemetry_ts: float | None = None
        self.world_objects: dict | None = None
        self.vision_objects: list = []

    def on_vision(self, data: dict):
        self.vision_objects = data.get("objects") or []

    def on_telemetry(self, data: dict, now: float):
        self.telemetry, self.telemetry_ts = data, now

    def on_world_objects(self, data: dict):
        self.world_objects = data

    def snapshot(self, now: float) -> dict:
        fresh = self.telemetry is not None and now - self.telemetry_ts <= TELEMETRY_STALE_S
        if self.world_objects is not None:
            objects = self.world_objects.get("objects") or []
            clusters = self.world_objects.get("clusters") or []
        else:
            objects, clusters = self.vision_objects, []
        return {
            "distance_cm": self.telemetry.get("distance_cm") if fresh else None,
            "override": bool(self.telemetry.get("override")) if fresh else False,
            "facing_id": self.facing_fn(objects, clusters),
        }


async def run(hub, config, *, clock=time.time, aggregator: RobotStateAggregator | None = None):
    agg = aggregator or RobotStateAggregator(config)

    async def on_vision(env):
        agg.on_vision(env.get("data") or {})

    async def on_telemetry(env):
        agg.on_telemetry(env.get("data") or {}, clock())

    async def on_objects(env):
        agg.on_world_objects(env.get("data") or {})

    async def on_reset(_env):
        agg.reset()

    hub.sub("vision.state", on_vision)
    hub.sub("robot.telemetry", on_telemetry)
    hub.sub("world.objects", on_objects)
    hub.sub("system.reset", on_reset)
    while True:
        await hub.pub("robot.state", agg.snapshot(clock()))
        await asyncio.sleep(1 / PUBLISH_HZ)
