"""T55 — robot state aggregator."""
import asyncio

from server.world import robot_state as mod
from server.world.robot_state import RobotStateAggregator


def fake_facing(objects, clusters=None):
    return objects[0]["id"] if objects else None


def test_merges_both_sources():
    agg = RobotStateAggregator(facing_fn=fake_facing)
    agg.on_vision({"objects": [{"id": 3, "pos": [0.6, 0.5]}], "giants": []})
    agg.on_telemetry({"distance_cm": 22, "line": [0, 0], "override": True}, now=10.0)
    s = agg.snapshot(10.5)
    assert s == {"distance_cm": 22, "override": True, "facing_id": 3}


def test_stale_telemetry_is_null():
    agg = RobotStateAggregator(facing_fn=fake_facing)
    agg.on_telemetry({"distance_cm": 22, "line": [0, 0], "override": True}, now=10.0)
    s = agg.snapshot(11.2)
    assert s["distance_cm"] is None and s["override"] is False
    assert agg.snapshot(10.9)["distance_cm"] == 22


def test_real_facing_uses_the_view():
    agg = RobotStateAggregator({"CAMERA_HFOV_DEG": 60})
    agg.on_world_objects({"objects": [{"id": 5, "pos": [0.5, 0.6], "size": [0.3, 0.4], "visible": True},
                                      {"id": 6, "pos": [0.5, 0.6], "size": [0.6, 0.6], "visible": False}],
                          "clusters": []})
    assert agg.snapshot(0)["facing_id"] == 5


def test_prefers_world_objects_for_facing():
    agg = RobotStateAggregator(facing_fn=fake_facing)
    agg.on_vision({"objects": [{"id": 3, "pos": [0.6, 0.5]}], "giants": []})
    agg.on_world_objects({"objects": [{"id": 9, "pos": [0.6, 0.5]}], "clusters": []})
    assert agg.snapshot(0)["facing_id"] == 9


def test_run_publishes_robot_state():
    class Hub:
        def __init__(self):
            self.subs, self.published = {}, []

        def sub(self, p, cb):
            self.subs[p] = cb

        async def pub(self, topic, data):
            self.published.append((topic, data))

    async def main():
        hub = Hub()
        agg = RobotStateAggregator(facing_fn=fake_facing)
        task = asyncio.create_task(mod.run(hub, {}, clock=lambda: 5.0, aggregator=agg))
        await asyncio.sleep(0)
        await hub.subs["robot.telemetry"]({"data": {"distance_cm": 30, "line": [0, 0], "override": False}})
        await asyncio.sleep(0.25)
        task.cancel()
        states = [d for t, d in hub.published if t == "robot.state"]
        assert len(states) >= 2 and states[-1]["distance_cm"] == 30

    asyncio.run(main())
