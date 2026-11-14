"""T48 — ObjectRegistry."""
import asyncio

from server.world.registry import ObjectRegistry

CFG = {"VIEW_GRACE_S": 0.5, "OBJECT_FORGET_S": 60}


def state(*objs):
    return {"frame_ts": 0, "objects": [{"id": i, "cls": "cup", "pos": list(p), "size": [0.05, 0.05], "conf": 0.9}
                                       for i, p in objs], "giants": []}


def test_new_id_added_exactly_once():
    reg = ObjectRegistry(CFG)
    assert reg.update(state((1, (0.5, 0.5))), 0.0).added == [1]
    for t in range(1, 10):
        assert reg.update(state((1, (0.5, 0.5))), t * 0.1).added == []
    obj = reg.get(1)
    assert obj.cls == "cup" and obj.first_seen == 0.0 and obj.last_seen == 0.9 and obj.visible


def test_out_of_view_is_kept_and_comes_back_as_itself():
    reg = ObjectRegistry(CFG)
    reg.update(state((1, (0.2, 0.5))), 0.0)
    assert reg.update(state(), 0.3).removed == [] and reg.get(1).visible  # one missed frame: still in view
    reg.update(state(), 1.0)
    obj = reg.get(1)
    assert obj is not None and obj.visible is False
    assert obj.pos == [0.2, 0.5]          # last place it was seen in the view
    assert reg.visible() == [] and len(reg.all()) == 1
    diff = reg.update(state((1, (0.8, 0.4))), 30.0)  # the robot turned back to it
    assert diff.added == [] and diff.removed == []
    assert reg.get(1).visible and reg.get(1).pos == [0.8, 0.4]


def test_forgotten_after_forget_s_exactly_once():
    reg = ObjectRegistry(CFG)
    reg.update(state((1, (0.5, 0.5))), 0.0)
    removed = []
    for t in [1, 10, 59.9]:
        removed += reg.update(state(), t).removed
    assert removed == []
    for t in [60.1, 61, 100]:
        removed += reg.update(state(), t).removed
    assert removed == [1]
    assert reg.get(1) is None


def test_visible_lists_only_what_is_in_view():
    reg = ObjectRegistry(CFG)
    reg.update(state((1, (0.2, 0.5)), (2, (0.7, 0.5))), 0.0)
    reg.update(state((2, (0.6, 0.5))), 1.0)
    assert [o.id for o in reg.visible()] == [2]
    assert sorted(o.id for o in reg.all()) == [1, 2]
    assert reg.get(1).to_dict()["visible"] is False


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
