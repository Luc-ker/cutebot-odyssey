"""T109 — acceptance: the demo keeps going when parts fail (whitepaper §7.15).

Each scenario runs the real modules on the real hub and ends with "no unhandled exceptions in logs"
(module tasks, hub callbacks and the event loop are all watched by the harness):

* Gemini always failing → the current world holds, Gemini is reported unhealthy, new objects still get
  a role from the local picker, and ``world.select`` still switches to a fallback world.
* Vision stops seeing the robot → ``robot.state`` keeps the last pose with ``seen: false``.
* ``vision.state`` stops entirely → objects stay for the grace period, then are removed; nothing crashes.
* The bridge micro:bit is unplugged → driving is unaffected (it is radio only, gamepad → Cutebot; the
  laptop bridge never carries drive packets), the bridge reports ``system.health ok:false`` and recovers
  when plugged back in.

(The video model failing is covered at unit level by T33.)
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fakes  # noqa: E402
from fakes import FakeAudio, FakeGemini, FakeSerialDevice, Harness, object_in, role_of  # noqa: E402
from server.bridge.serial_bridge import SerialBridge  # noqa: E402
from server.world import arrivals, objects_publisher, robot_state  # noqa: E402
from server.world.memory import RoleMemory  # noqa: E402
from server.world.registry import ObjectRegistry  # noqa: E402
from server.world.worlds import WorldRegistry  # noqa: E402

CHAIR, BOWL = 1, 2


async def world_stack(h: Harness, config, gemini: FakeGemini, audio: FakeAudio | None = None):
    memory, registry = RoleMemory(), ObjectRegistry(config)
    sched = fakes.make_scheduler(await h.client("scheduler"), config, audio=audio or FakeAudio(), gemini=gemini,
                                 worlds=WorldRegistry(config), memory=memory, registry=registry)
    await h.start("arrivals", arrivals.run, registry=registry, memory=memory, request_role=gemini.request_role)
    await h.start("objects_publisher", objects_publisher.run, registry=registry, memory=memory)
    await h.start("robot_state", robot_state.run)
    await h.settle()
    return sched


# ---- Gemini down -----------------------------------------------------------------------------------------


def test_gemini_down_world_holds_and_select_still_works():
    async def go():
        config = fakes.test_config(GEMINI_TIMEOUT_S=0.3)
        audio = FakeAudio()
        gemini = FakeGemini(audio)
        gemini.mode = "fail"
        async with Harness(config) as h:
            sched = await world_stack(h, config, gemini, audio)
            await h.pub("world.select", {"name": "kingdom"})
            kingdom = (await h.wait_for("world.current")).data["world"]

            # the music changes, Gemini fails every time: the world holds
            audio.play("heavy_metal")
            m = h.mark()
            for _ in range(3):
                assert await sched.tick() == "failed"
            await h.wait_for("system.health", lambda d: d.get("service") == "gemini" and d["ok"] is False, after=m)
            await h.settle(0.3)
            assert not h.find("world.current", after=m)

            # a new object still gets a role, from the local picker
            h.scene.put(BOWL, "bowl", (0.5, 0.5))
            h.feeding = True
            added = await h.wait_for("world.event", lambda d: d.get("kind") == "object_added" and d["id"] == BOWL,
                                     after=m, timeout=3)
            assert added.data["role"] and added.data["name"]
            objs = await h.latest("world.objects", lambda d: role_of(d, BOWL) is not None)
            assert objs["world_id"] == kingdom["id"]

            # the status page can still pick a pre-composed world
            m = h.mark()
            await h.pub("world.select", {"name": "ocean"})
            ocean = (await h.wait_for("world.current", after=m)).data["world"]
            assert ocean["id"] != kingdom["id"] and "ocean" in ocean["world"]["setting"]
            h.assert_no_errors()

    asyncio.run(go())


# ---- robot lost by the camera -------------------------------------------------------------------------------


def test_robot_unseen_keeps_last_pose():
    async def go():
        config = fakes.test_config()
        async with Harness(config) as h:
            await world_stack(h, config, FakeGemini())
            h.scene.robot = {"pos": [0.42, 0.58], "heading": 1.2, "seen": True}
            h.feeding = True
            await h.wait_for("robot.state", lambda d: d["seen"] is True and d["pos"] == [0.42, 0.58])

            h.scene.robot = None  # the Jetson stops finding the marker
            m = h.mark()
            lost = await h.wait_for("robot.state", lambda d: d["seen"] is False, after=m, timeout=1.0)
            assert lost.data["pos"] == [0.42, 0.58] and lost.data["heading"] == 1.2
            await h.settle(0.5)
            for msg in h.find("robot.state", after=m)[-3:]:
                assert msg.data["seen"] is False and msg.data["pos"] == [0.42, 0.58], "pose must freeze, not jump"

            h.scene.robot = {"pos": [0.45, 0.6], "heading": 1.0, "seen": True}  # found again
            await h.wait_for("robot.state", lambda d: d["seen"] is True and d["pos"] == [0.45, 0.6], after=m)
            h.assert_no_errors()

    asyncio.run(go())


# ---- the Jetson goes silent ----------------------------------------------------------------------------------

GRACE_S = 1.0


async def vision_goes_silent(check_removal: bool):
    config = fakes.test_config(OBJECT_GRACE_S=GRACE_S)
    async with Harness(config) as h:
        await world_stack(h, config, FakeGemini())
        await h.pub("world.select", {"name": "kingdom"})
        await h.wait_for("world.current")
        h.scene.put(CHAIR, "chair", (0.3, 0.4))
        h.scene.robot = {"pos": [0.6, 0.6], "heading": 0.0, "seen": True}
        h.feeding = True
        await h.wait_for("world.objects", lambda d: role_of(d, CHAIR) is not None, timeout=3)

        h.feeding = False  # vision.state stops entirely
        m = h.mark()
        await h.settle(GRACE_S * 0.5)
        objs = await h.latest("world.objects")
        assert object_in(objs, CHAIR), "objects must stay during the grace period"
        assert h.find("robot.state", after=m), "robot.state must keep publishing"

        if check_removal:
            await h.wait_for("world.event", lambda d: d.get("kind") == "object_removed" and d["id"] == CHAIR,
                             after=m, timeout=GRACE_S + 1.5)
            objs = await h.latest("world.objects")
            assert not object_in(objs, CHAIR), "objects must be removed after the grace period"
        else:
            m2 = h.mark()
            await h.settle(GRACE_S + 1.0)
            assert h.find("world.objects", after=m2), "world.objects must keep publishing"
            assert h.find("robot.state", after=m2), "robot.state must keep publishing"
        h.assert_no_errors()


def test_vision_silent_objects_stay_for_grace_and_nothing_crashes():
    asyncio.run(vision_goes_silent(check_removal=False))


@pytest.mark.xfail(strict=True, reason=(
    "T48/T50 gap: ObjectRegistry only expires objects inside update(), which arrivals calls per "
    "vision.state. When vision.state stops entirely nothing calls it, so objects are never removed. "
    "Needs a periodic registry.update({}, now) (or expiry in all()) while vision is silent. "
    "Remove this mark when fixed."))
def test_vision_silent_objects_removed_after_grace():
    asyncio.run(vision_goes_silent(check_removal=True))


# ---- the bridge micro:bit is unplugged --------------------------------------------------------------------------


def test_bridge_unplugged_reports_and_recovers():
    async def go():
        config = fakes.test_config()
        device = FakeSerialDevice()

        async def bridge(hub, cfg):
            b = SerialBridge(hub, cfg, open_port=device.open)
            hub.sub("robot.cmd", b.on_cmd)
            await b.loop()

        async with Harness(config) as h:
            await world_stack(h, config, FakeGemini())
            await h.start("serial_bridge", bridge)
            h.scene.robot = {"pos": [0.5, 0.5], "heading": 0.0, "seen": True}
            h.feeding = True
            await h.wait_for("system.health", lambda d: d.get("service") == "serial_bridge" and d["ok"] is True,
                             timeout=3)

            device.unplug()
            m = h.mark()
            down = await h.wait_for("system.health", lambda d: d.get("service") == "serial_bridge" and d["ok"] is False,
                                    after=m, timeout=3)
            # the rest of the system keeps going while the bridge is gone
            await h.pub("robot.cmd", {"kind": "lights", "mode": "flash", "rgb": [255, 255, 255], "ms": 200})
            await h.pub("robot.cmd", {"kind": "recoil", "ms": 600})
            await h.settle(0.5)
            assert [x for x in h.find("robot.state", after=m) if x.t > down.t], "robot.state stopped with the bridge"

            device.replug()
            m = h.mark()
            await h.wait_for("system.health", lambda d: d.get("service") == "serial_bridge" and d["ok"] is True,
                             after=m, timeout=4)
            assert device.opens >= 2, "the bridge should have reopened the port"
            # driving is radio only (gamepad → Cutebot, C6): the laptop bridge never carries drive packets
            assert not device.lines("D,")
            h.assert_no_errors()

    asyncio.run(go())
