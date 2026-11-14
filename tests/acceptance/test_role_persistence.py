"""T106 — acceptance: an object keeps its role (whitepaper §7.4, §12 "the chair is a castle, and it stays a castle").

End to end through the real hub with the real world modules (registry T48, memory T49, arrivals T50,
objects publisher T62, robot state T55), the scheduler stand-in selecting the ``kingdom`` fallback world,
and a fake Gemini that gives a *different* name every time it is asked. A table with a chair is fed as
``vision.state``; the chair's role must survive:

1. the robot driving away and back,
2. the chair being moved (and the map following within half a second, §10),
3. the chair being hidden for 2 s (inside the grace period), and
4. the chair being hidden for 2 s with a 1 s grace period, so it is dropped and comes back as "new".

Step 4 can only pass if ``RoleMemory`` remembers; ``test_detects_forgetful_memory`` proves the scenario fails
when RoleMemory is replaced by a stub that forgets.
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fakes  # noqa: E402
from fakes import FakeGemini, Harness, role_of, object_in  # noqa: E402
from server.world import arrivals, objects_publisher, robot_state  # noqa: E402
from server.world.memory import RoleMemory  # noqa: E402
from server.world.registry import ObjectRegistry  # noqa: E402
from server.world.worlds import WorldRegistry  # noqa: E402

CHAIR = 1
CHAIR_AT = (0.30, 0.40)
MOVED_TO = (0.70, 0.65)


class ForgetfulMemory(RoleMemory):
    """A RoleMemory that keeps the current roles but cannot recall an earlier assignment, so an object that
    comes back is treated as brand new (for the negative check)."""

    def get(self, world_id, obj_id):
        return None


async def chair_role(h: Harness, timeout=3.0):
    data = await h.latest("world.objects", lambda d: role_of(d, CHAIR) is not None, timeout=timeout)
    return role_of(data, CHAIR)


async def scenario(memory: RoleMemory, grace_s: float = 5.0):
    config = fakes.test_config(OBJECT_GRACE_S=grace_s)
    gemini = FakeGemini()
    registry = ObjectRegistry(config)
    async with Harness(config) as h:
        sched = fakes.make_scheduler(await h.client("scheduler"), config, audio=fakes.FakeAudio(),
                                     gemini=gemini, worlds=WorldRegistry(config), memory=memory,
                                     registry=registry)
        await h.start("arrivals", arrivals.run, registry=registry, memory=memory,
                      request_role=gemini.request_role)
        await h.start("objects_publisher", objects_publisher.run, registry=registry, memory=memory)
        await h.start("robot_state", robot_state.run)
        await h.settle()

        # select the kingdom, put a chair on the table, robot near it
        await h.pub("world.select", {"name": "kingdom"})
        world = (await h.wait_for("world.current")).data["world"]
        assert "kingdom" in (world["world"]["setting"] + world.get("key", "")).lower()
        h.scene.put(CHAIR, "chair", CHAIR_AT, (0.12, 0.14))
        h.scene.robot = {"pos": [0.35, 0.5], "heading": 0.0, "seen": True}
        h.feeding = True
        added = await h.wait_for("world.event", lambda d: d.get("kind") == "object_added" and d["id"] == CHAIR,
                                 timeout=5)
        first = await chair_role(h)
        assert first == (added.data["role"], added.data["name"], added.data["behaviour"])
        assert h.snapshot.requests >= 1, "arrivals should fetch the overhead snapshot for Gemini"

        # 1. drive away and back
        for pos in ([0.9, 0.9], [0.9, 0.1], [0.35, 0.5]):
            h.scene.robot = {"pos": pos, "heading": 1.0, "seen": True}
            await h.settle(0.3)
        assert await chair_role(h) == first, "role changed after the robot drove away and back"

        # 2. move the chair: the map follows within half a second and the role is unchanged
        h.scene.move(CHAIR, MOVED_TO)
        moved = await h.wait_for("world.objects",
                                 lambda d: (o := object_in(d, CHAIR)) and abs(o["pos"][0] - MOVED_TO[0]) < 1e-6,
                                 after=h.mark(), timeout=0.5 + 0.2)
        assert role_of(moved.data, CHAIR) == first, "role changed after the chair moved"

        # 3./4. hide it for 2 s, then put it back
        hidden = h.scene.hide(CHAIR)
        await h.settle(2.0)
        h.scene.objects[CHAIR] = hidden
        await h.settle(0.6)
        assert await chair_role(h, timeout=4) == first, "role changed after the chair was hidden for 2 s"
        h.assert_no_errors()
        return gemini


def test_role_survives_driving_moving_and_short_hiding():
    gemini = asyncio.run(scenario(RoleMemory(), grace_s=5.0))
    assert gemini.role_calls == 1, "the chair should only ever be asked about once"


def test_role_survives_being_dropped_and_coming_back():
    # 1 s grace: the 2 s hide drops the chair from the registry; it comes back as a "new" object and only
    # RoleMemory can give it its old role back.
    gemini = asyncio.run(scenario(RoleMemory(), grace_s=1.0))
    assert gemini.role_calls == 1, "a remembered object must not need a new Gemini call"


def test_detects_forgetful_memory():
    with pytest.raises(AssertionError, match="role changed after the chair was hidden"):
        asyncio.run(scenario(ForgetfulMemory(), grace_s=1.0))
