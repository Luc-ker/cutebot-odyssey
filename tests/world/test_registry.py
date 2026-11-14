"""T48 — ObjectRegistry."""
import asyncio

from server.world.registry import ObjectRegistry

CFG = {"OBJECT_GRACE_S": 5, "TABLE_W_CM": 100, "TABLE_H_CM": 100}


def state(*objs):
    return {"frame_ts": 0, "objects": [{"id": i, "cls": "cup", "pos": list(p), "size": [0.05, 0.05], "conf": 0.9}
                                       for i, p in objs], "robot": None, "giants": []}


def test_new_id_added_exactly_once():
    reg = ObjectRegistry(CFG)
    assert reg.update(state((1, (0.5, 0.5))), 0.0).added == [1]
    for t in range(1, 10):
        assert reg.update(state((1, (0.5, 0.5))), t * 0.1).added == []
    obj = reg.get(1)
    assert obj.cls == "cup" and obj.first_seen == 0.0 and obj.last_seen == 0.9


def test_short_absence_kept_long_absence_removed_once():
    reg = ObjectRegistry(CFG)
    reg.update(state((1, (0.5, 0.5))), 0.0)
    removed = []
    for t in [1, 2, 3, 4, 4.9]:
        removed += reg.update(state(), t).removed
    assert removed == [] and reg.get(1) is not None and len(reg.all()) == 1
    reg.update(state((1, (0.5, 0.5))), 5.0)  # came back inside the grace period
    assert reg.update(state(), 9.0).removed == []
    removed = []
    for t in [10.1, 11, 12, 20]:
        removed += reg.update(state(), t).removed
    assert removed == [1]
    assert reg.get(1) is None


def test_moved_over_two_cm():
    reg = ObjectRegistry(CFG)
    reg.update(state((1, (0.5, 0.5))), 0)
    assert reg.update(state((1, (0.51, 0.5))), 1).moved == []   # 1 cm
    assert reg.update(state((1, (0.525, 0.5))), 2).moved == [1]  # 2.5 cm from the anchor
    assert reg.update(state((1, (0.535, 0.5))), 3).moved == []   # 1 cm since last move


def test_slow_drift_adds_up():
    reg = ObjectRegistry(CFG)
    reg.update(state((1, (0.5, 0.5))), 0)
    moved = []
    for i in range(1, 6):
        moved += reg.update(state((1, (0.5 + i * 0.005, 0.5))), i).moved
    assert moved == [1]


def test_clear_on_system_reset():
    from server.world import registry as mod

    class Hub:
        def __init__(self):
            self.subs = {}

        def sub(self, pattern, cb):
            self.subs[pattern] = cb

    reg = ObjectRegistry(CFG)
    reg.update(state((1, (0.5, 0.5))), 0)
    hub = Hub()
    asyncio.run(mod.run(hub, CFG, registry=reg))
    asyncio.run(hub.subs["system.reset"]({"topic": "system.reset", "data": {}}))
    assert reg.all() == []
    assert reg.update(state((1, (0.5, 0.5))), 1).added == [1]
