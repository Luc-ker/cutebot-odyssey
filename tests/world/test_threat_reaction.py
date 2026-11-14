"""T58 — threat reaction."""
import asyncio

from server.world import threat_reaction as mod
from server.world.threat_reaction import ThreatReaction

ENTER = {"kind": "danger_enter", "id": 5, "name": "Ember", "role": "dragon"}


def test_one_enter_one_of_each():
    out = ThreatReaction({"RECOIL_MS": 700}).on_event(ENTER, 0.0)
    assert out == [("robot.cmd", {"kind": "recoil", "ms": 700}),
                   ("sfx.play", {"sound": "warning"}),
                   ("robot.cmd", {"kind": "rumble", "ms": 300})]


def test_second_enter_within_cooldown_does_nothing():
    r = ThreatReaction()
    assert r.on_event(ENTER, 0.0)
    assert r.on_event(dict(ENTER, id=6), 1.0) == []
    assert r.on_event(ENTER, 2.6)


def test_ignores_other_events_and_publishes_via_hub():
    class Hub:
        def __init__(self):
            self.subs, self.published = {}, []

        def sub(self, p, cb):
            self.subs[p] = cb

        async def pub(self, topic, data):
            self.published.append((topic, data))

    async def main():
        hub = Hub()
        await mod.run(hub, {}, clock=lambda: 0.0)
        await hub.subs["world.event"]({"data": {"kind": "friendly_enter", "id": 1}})
        assert hub.published == []
        await hub.subs["world.event"]({"data": ENTER})
        topics = [t for t, _ in hub.published]
        assert topics == ["robot.cmd", "sfx.play", "robot.cmd"]
        assert not any(d.get("kind") == "lights" for _, d in hub.published)

    asyncio.run(main())
