"""T50 — new and removed object flow."""
import asyncio
import time

from server.world.arrivals import Arrivals
from server.world.memory import RoleMemory
from server.world.registry import ObjectRegistry

WORLD = {"id": "w-0000beef", "world": {"name": "The Salt Sea", "setting": "open ocean", "mood": "bright"},
         "roles": [], "narration": "Ahoy."}
STUB_VOCAB = [{"role": "lighthouse", "behaviour": "friendly", "worlds": ["ocean"], "classes": ["bottle"]}]


class FakeHub:
    def __init__(self):
        self.subs, self.published = [], []

    def sub(self, pattern, cb):
        self.subs.append((pattern, cb))

    async def pub(self, topic, data):
        self.published.append((topic, data))
        for p, cb in list(self.subs):
            if p == topic or (p.endswith("*") and topic.startswith(p[:-1])):
                await cb({"topic": topic, "ts": time.time(), "src": "test", "data": data})

    def events(self, kind):
        return [d for t, d in self.published if t == "world.event" and d.get("kind") == kind]


def vstate(objs=(), giants=()):
    return {"frame_ts": 0, "objects": [{"id": i, "cls": c, "pos": [0.5, 0.5], "size": [0.05, 0.05], "conf": 1}
                                       for i, c in objs],
            "robot": None, "giants": list(giants)}


async def _no_snapshot():
    return b"jpeg"


def make(request_role=None, timeout=4.0, clock=time.time):
    hub = FakeHub()
    arr = Arrivals(hub, {"OBJECT_GRACE_S": 5}, registry=ObjectRegistry({"OBJECT_GRACE_S": 5}),
                   memory=RoleMemory(), request_role=request_role, vocab=STUB_VOCAB,
                   fetch_snapshot=_no_snapshot, clock=clock, gemini_timeout_s=timeout).attach()
    return hub, arr


async def _settle(arr):
    while arr._tasks:
        await asyncio.gather(*list(arr._tasks), return_exceptions=True)


def test_gemini_timeout_uses_local_picker_within_5s():
    async def hanging(world, obj, image):
        await asyncio.sleep(60)

    async def main():
        hub, arr = make(request_role=hanging)  # the real 4 s timeout, as specified
        await hub.pub("world.current", {"world": WORLD, "previous_id": None})
        t0 = time.monotonic()
        await hub.pub("vision.state", vstate([(1, "bottle")]))
        await _settle(arr)
        elapsed = time.monotonic() - t0
        added = hub.events("object_added")
        assert len(added) == 1 and elapsed < 5.0
        assert added[0]["role"] == "lighthouse" and added[0]["from_sky"] is False
        assert added[0]["announce"]
        assert arr.memory.get(WORLD["id"], 1)["role"] == "lighthouse"

    asyncio.run(main())


def test_gemini_result_used_and_announce_passed_on():
    async def gemini(world, obj, image):
        assert image == b"jpeg" and obj["cls"] == "bottle"
        return {"role": "ship", "name": "The Salt Queen", "behaviour": "neutral", "announce": "A ship!"}

    async def main():
        hub, arr = make(request_role=gemini)
        await hub.pub("world.current", {"world": WORLD, "previous_id": None})
        await hub.pub("vision.state", vstate([(1, "bottle")]))
        await _settle(arr)
        (ev,) = hub.events("object_added")
        assert (ev["role"], ev["name"], ev["announce"]) == ("ship", "The Salt Queen", "A ship!")

    asyncio.run(main())


def test_remembered_role_skips_gemini():
    async def gemini(world, obj, image):
        raise AssertionError("should not be called")

    async def main():
        hub, arr = make(request_role=gemini)
        arr.memory.set(WORLD["id"], 1, {"role": "castle", "name": "Old Keep", "behaviour": "neutral"})
        await hub.pub("world.current", {"world": WORLD, "previous_id": None})
        await hub.pub("vision.state", vstate([(1, "bottle")]))
        await _settle(arr)
        assert hub.events("object_added")[0]["name"] == "Old Keep"

    asyncio.run(main())


def test_from_sky_when_giant_present():
    async def main():
        hub, arr = make()
        await hub.pub("world.current", {"world": WORLD, "previous_id": None})
        giant = {"id": 9, "kind": "hand", "pos": [0.5, 0.1], "size": [0.2, 0.2], "edge": "top"}
        await hub.pub("vision.state", vstate([], [giant]))
        await hub.pub("vision.state", vstate([(1, "bottle")], [giant]))
        await _settle(arr)
        assert hub.events("object_added")[0]["from_sky"] is True

    asyncio.run(main())


def test_from_sky_window_is_three_seconds():
    now = [100.0]

    async def main():
        hub, arr = make(clock=lambda: now[0])
        await hub.pub("world.current", {"world": WORLD, "previous_id": None})
        await hub.pub("vision.state", vstate([], [{"pos": [0.5, 0.1], "kind": "hand", "edge": "top"}]))
        now[0] += 2.5
        await hub.pub("vision.state", vstate([(1, "bottle")]))
        now[0] += 1.0
        await hub.pub("vision.state", vstate([(1, "bottle"), (2, "bottle")]))
        await _settle(arr)
        flags = {e["id"]: e["from_sky"] for e in hub.events("object_added")}
        assert flags == {1: True, 2: False}

    asyncio.run(main())


def test_at_most_two_gemini_calls_in_flight():
    calls = []

    async def slow(world, obj, image):
        calls.append(obj["id"])
        await asyncio.sleep(0.2)
        return {"role": "ship", "name": "Ship %d" % obj["id"], "behaviour": "neutral"}

    async def main():
        hub, arr = make(request_role=slow)
        await hub.pub("world.current", {"world": WORLD, "previous_id": None})
        await hub.pub("vision.state", vstate([(i, "bottle") for i in range(1, 6)]))
        await _settle(arr)
        added = hub.events("object_added")
        assert len(calls) == 2 and len(added) == 5
        assert sum(1 for e in added if e["role"] == "ship") == 2

    asyncio.run(main())


def test_pending_until_world_then_removed_after_grace():
    now = [0.0]

    async def main():
        hub, arr = make(clock=lambda: now[0])
        await hub.pub("vision.state", vstate([(1, "bottle")]))  # no world yet
        await _settle(arr)
        assert hub.events("object_added") == []
        await hub.pub("world.current", {"world": WORLD, "previous_id": None})
        await _settle(arr)
        assert len(hub.events("object_added")) == 1
        now[0] = 10.0
        await hub.pub("vision.state", vstate([]))
        await _settle(arr)
        assert hub.events("object_removed") == [{"kind": "object_removed", "id": 1}]

    asyncio.run(main())


def test_reset_clears_state():
    async def main():
        hub, arr = make()
        await hub.pub("world.current", {"world": WORLD, "previous_id": None})
        await hub.pub("vision.state", vstate([(1, "bottle")]))
        await _settle(arr)
        await hub.pub("system.reset", {})
        assert arr.registry.all() == [] and arr.world is None

    asyncio.run(main())
