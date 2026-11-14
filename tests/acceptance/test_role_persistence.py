"""T106 — acceptance: an object keeps its role (whitepaper §7.4, §12 "the chair is a castle, and it stays a castle").

End to end through the real hub with the real world modules (registry T48, memory T49, arrivals T50,
objects publisher T62, robot state T55), the scheduler stand-in selecting the ``kingdom`` fallback world,
and a fake Gemini that gives a *different* name every time it is asked. The robot's view of a chair is fed as
``vision.state``; the chair's role must survive:

1. the robot turning away (the chair leaves the view) and back (it comes back, re-identified, on the other
   side of the view),
2. the chair sliding across the view (and ``world.objects`` following within half a second, §10),
3. the chair being out of view for 2 s (well inside ``OBJECT_FORGET_S``), and
4. the chair being out of view for 2 s with a 1 s ``OBJECT_FORGET_S``, so it is forgotten and comes back as
   "new".

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


async def scenario(memory: RoleMemory, forget_s: float = 5.0):
    config = fakes.test_config(OBJECT_FORGET_S=forget_s, VIEW_GRACE_S=0.3)
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

        # select the kingdom, the robot looks at a chair
        await h.pub("world.select", {"name": "kingdom"})
        world = (await h.wait_for("world.current")).data["world"]
        assert "kingdom" in (world["world"]["setting"] + world.get("key", "")).lower()
        h.scene.put(CHAIR, "chair", CHAIR_AT, (0.12, 0.14))
        h.feeding = True
        added = await h.wait_for("world.event", lambda d: d.get("kind") == "object_added" and d["id"] == CHAIR,
                                 timeout=5)
        first = await chair_role(h)
        assert first == (added.data["role"], added.data["name"], added.data["behaviour"])
        assert h.snapshot.requests >= 1, "arrivals should fetch the robot's-view snapshot for Gemini"

        # 1. turn away (out of view, but still known) and back (in view on the other side)
        away = h.scene.hide(CHAIR)
        out = await h.wait_for("world.objects", lambda d: (o := object_in(d, CHAIR)) and o["visible"] is False,
                               after=h.mark(), timeout=2)
        assert role_of(out.data, CHAIR) == first, "an object out of view must keep its role"
        h.scene.objects[CHAIR] = dict(away, pos=[0.85, 0.45])
        await h.settle(0.3)
        assert await chair_role(h) == first, "role changed after the robot turned away and back"

        # 2. the chair slides across the view: world.objects follows within half a second, the role is unchanged
        h.scene.move(CHAIR, MOVED_TO)
        moved = await h.wait_for("world.objects",
                                 lambda d: (o := object_in(d, CHAIR)) and abs(o["pos"][0] - MOVED_TO[0]) < 1e-6,
                                 after=h.mark(), timeout=0.5 + 0.2)
        assert role_of(moved.data, CHAIR) == first, "role changed after the chair moved"

        # 3./4. out of view for 2 s, then back
        hidden = h.scene.hide(CHAIR)
        await h.settle(2.0)
        h.scene.objects[CHAIR] = hidden
        await h.settle(0.6)
        assert await chair_role(h, timeout=4) == first, "role changed after the chair was out of view for 2 s"
        h.assert_no_errors()
        return gemini


def test_role_survives_turning_away_moving_and_short_absence():
    gemini = asyncio.run(scenario(RoleMemory(), forget_s=5.0))
    assert gemini.role_calls == 1, "the chair should only ever be asked about once"


def test_role_survives_being_forgotten_and_coming_back():
    # 1 s OBJECT_FORGET_S: 2 s out of view drops the chair from the registry; it comes back as a "new" object
    # and only RoleMemory can give it its old role back.
    gemini = asyncio.run(scenario(RoleMemory(), forget_s=1.0))
    assert gemini.role_calls == 1, "a remembered object must not need a new Gemini call"


def test_detects_forgetful_memory():
    with pytest.raises(AssertionError, match="role changed after the chair was out of view"):
        asyncio.run(scenario(ForgetfulMemory(), forget_s=1.0))
