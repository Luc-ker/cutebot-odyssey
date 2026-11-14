"""T95 — world transition coordinator."""
import asyncio

from server.world import transitions as mod
from server.world.transitions import TransitionCoordinator

SEA = {"id": "w-0000beef", "world": {"name": "The Salt Sea"}}
FIRE = {"id": "w-0000f1re", "world": {"name": "Ashlands"}}
SNOW = {"id": "w-00005n0w", "world": {"name": "Hush"}}


class FakeHub:
    def __init__(self):
        self.subs, self.published = [], []

    def sub(self, pattern, cb):
        self.subs.append((pattern, cb))

    async def pub(self, topic, data):
        self.published.append((topic, data))
        for p, cb in list(self.subs):
            if p == topic or (p.endswith("*") and topic.startswith(p[:-1])):
                await cb({"topic": topic, "ts": 0.0, "src": "test", "data": data})


def test_same_id_twice_gives_one_transition():
    async def main():
        hub = FakeHub()
        await mod.run(hub, {"TRANSITION_MS": 2500}, clock=lambda: 100.0)
        await hub.pub("world.current", {"world": SEA, "previous_id": None})
        await hub.pub("world.current", {"world": SEA, "previous_id": None})
        trans = [d for t, d in hub.published if t == "world.transition"]
        assert trans == [{"from": None, "to": SEA, "started": 100.0, "duration_ms": 2500}]

    asyncio.run(main())


def test_change_goes_from_previous_world():
    c = TransitionCoordinator(3000)
    c.on_world(SEA, 0.0)
    out = c.on_world(FIRE, 10.0)
    assert out["from"] == SEA and out["to"] == FIRE and out["started"] == 10.0


def test_mid_transition_change_starts_from_current_target():
    c = TransitionCoordinator(3000)
    c.on_world(SEA, 0.0)
    c.on_world(FIRE, 10.0)
    assert c.in_transition(11.0)
    out = c.on_world(SNOW, 11.0)
    assert out["from"] == FIRE and out["to"] == SNOW and out["started"] == 11.0
    assert c.on_world(SNOW, 11.5) is None


def test_repeat_during_transition_is_ignored():
    c = TransitionCoordinator(3000)
    c.on_world(SEA, 0.0)
    assert c.on_world(SEA, 1.0) is None
    assert c.on_world(SEA, 5.0) is None
    assert not c.in_transition(5.0)


def test_repeat_refreshes_from_copy():
    c = TransitionCoordinator()
    c.on_world(SEA, 0.0)
    updated = dict(SEA, narration="new line")
    c.on_world(updated, 5.0)
    assert c.on_world(FIRE, 6.0)["from"] == updated


def test_reset_forgets_world():
    async def main():
        hub = FakeHub()
        await mod.run(hub, {}, clock=lambda: 1.0)
        await hub.pub("world.current", {"world": SEA, "previous_id": None})
        await hub.pub("system.reset", {})
        await hub.pub("world.current", {"world": SEA, "previous_id": None})
        trans = [d for t, d in hub.published if t == "world.transition"]
        assert len(trans) == 2 and trans[1]["from"] is None
        assert trans[1]["duration_ms"] == mod.DEFAULT_TRANSITION_MS

    asyncio.run(main())


def test_bad_input_ignored():
    c = TransitionCoordinator()
    assert c.on_world(None, 0.0) is None
    assert c.on_world({"world": {}}, 0.0) is None
