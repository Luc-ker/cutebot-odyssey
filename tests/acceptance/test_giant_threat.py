"""T108 — acceptance: the demo's big moment (whitepaper §7.10, §7.11, §12 "1:05–1:25").

A hand on the table becomes a giant (with a narration line); an object dropped while the hand is there arrives
"from the sky" and, forced by the fake Gemini, is a threat; driving the robot into its danger radius makes it
recoil: ``robot.cmd recoil``, ``sfx.play warning``, a red light flash, and an ``R,<ms>`` packet on the bridge
micro:bit's serial port.

Real hub and real modules: arrivals (T50), objects publisher (T62), giants (T61), robot state (T55),
proximity (T57), threat reaction (T58), light director (T23), serial bridge (T22, on a fake port),
narration triggers (T82) and queue (T79). Time limits come from §10: a new object is announced within a
few seconds; the threat reaction reaches the serial port well inside the 100 ms-class "immediate" budget
(asserted at 500 ms to leave room for CI jitter).
"""

import asyncio
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

import fakes  # noqa: E402
from fakes import FakeGemini, FakeSerialDevice, Harness, object_in  # noqa: E402
from server.bridge import light_director  # noqa: E402
from server.bridge.serial_bridge import SerialBridge  # noqa: E402
from server.narration import queue as narration_queue  # noqa: E402
from server.narration import triggers as narration_triggers  # noqa: E402
from server.world import arrivals, giants, objects_publisher, proximity, robot_state, threat_reaction  # noqa: E402
from server.world.memory import RoleMemory  # noqa: E402
from server.world.registry import ObjectRegistry  # noqa: E402
from server.world.worlds import WorldRegistry  # noqa: E402

CHAIR, CRISPS = 1, 7
CRISPS_AT = (0.60, 0.50)
HAND = {"id": 1, "kind": "hand", "pos": [0.62, 0.22], "size": [0.12, 0.16], "edge": "top"}
THREAT = {"role": "dragon", "name": "the Crisp Wyrm", "behaviour": "threat",
          "announce": "A dragon of crackling foil drops from the sky!"}

ANNOUNCE_WITHIN_S = 3.0   # §10 "new object to role assigned and announced: a few seconds"
GIANT_WITHIN_S = 1.0      # 300 ms debounce (T61) plus hub hops
REACT_WITHIN_S = 0.5      # danger_enter → recoil / warning / red light / serial R packet


def bridge_run(device: FakeSerialDevice):
    """The serial bridge's own ``run``, with the fake port plugged in."""

    async def run(hub, config):
        bridge = SerialBridge(hub, config, open_port=device.open)
        hub.sub("robot.cmd", bridge.on_cmd)
        await bridge.loop()

    return run


async def run_big_moment(check_serial: bool):
    config = fakes.test_config()
    gemini = FakeGemini()
    memory, registry = RoleMemory(), ObjectRegistry(config)
    device = FakeSerialDevice()

    async with Harness(config) as h:
        fakes.make_scheduler(await h.client("scheduler"), config, audio=fakes.FakeAudio(), gemini=gemini,
                             worlds=WorldRegistry(config), memory=memory, registry=registry)
        await h.start("arrivals", arrivals.run, registry=registry, memory=memory, request_role=gemini.request_role)
        await h.start("objects_publisher", objects_publisher.run, registry=registry, memory=memory)
        await h.start("giants", giants.run)
        await h.start("robot_state", robot_state.run)
        await h.start("proximity", proximity.run)
        await h.start("threat_reaction", threat_reaction.run)
        await h.start("light_director", light_director.run)
        await h.start("serial_bridge", bridge_run(device))
        await h.start("narration_triggers", narration_triggers.run)
        await h.start("narration_queue", narration_queue.run)
        await h.start("sound_page", fakes.fake_speaker())
        await h.settle()

        await h.pub("world.select", {"name": "kingdom"})
        await h.wait_for("world.current")
        h.scene.put(CHAIR, "chair", (0.25, 0.30), (0.12, 0.14))
        h.scene.robot = {"pos": [0.10, 0.90], "heading": 0.0, "seen": True}
        h.feeding = True
        await h.wait_for("world.event", lambda d: d.get("kind") == "object_added" and d["id"] == CHAIR, timeout=5)
        await h.settle(0.5)

        # ---- a hand reaches over the table → a giant, and the narrator says so ---------------------------
        m = h.mark()
        h.scene.giants = [dict(HAND)]
        enter = await h.wait_for("world.event", lambda d: d.get("kind") == "giant_enter", after=m,
                                 timeout=GIANT_WITHIN_S)
        assert enter.data.get("edge") == "top"
        say = await h.wait_for("narration.say", lambda d: "titan" in d["text"].lower() or "giant" in d["text"].lower(),
                               after=m, timeout=1.0)
        assert say.t >= enter.t
        await h.wait_for("narration.speak", lambda d: d["text"] == say.data["text"], after=m, timeout=1.0)

        # ---- drop a crisp packet while the hand is there → from the sky, a threat -------------------------
        gemini.forced_role = dict(THREAT)
        m = h.mark()
        h.scene.put(CRISPS, "object", CRISPS_AT, (0.06, 0.05))
        dropped_at = h.messages[-1].t if h.messages else 0.0
        added = await h.wait_for("world.event", lambda d: d.get("kind") == "object_added" and d["id"] == CRISPS,
                                 after=m, timeout=ANNOUNCE_WITHIN_S)
        assert added.data["from_sky"] is True
        assert added.data["behaviour"] == "threat" and added.data["role"] == "dragon"
        assert added.t - dropped_at <= ANNOUNCE_WITHIN_S
        await h.wait_for("world.objects", lambda d: (o := object_in(d, CRISPS)) and o["behaviour"] == "threat"
                         and o["from_sky"] is True, after=m, timeout=1.0)
        await h.wait_for("narration.say", lambda d: d["text"] == THREAT["announce"], after=m, timeout=1.0)

        # the hand leaves
        h.scene.giants = []
        await h.wait_for("world.event", lambda d: d.get("kind") == "giant_leave", after=m, timeout=2.0)

        # ---- drive into the danger radius → recoil ---------------------------------------------------------
        m = h.mark()
        serial_mark = len(device.written)
        start, end = h.scene.robot["pos"], [CRISPS_AT[0] - 0.05, CRISPS_AT[1] + 0.05]
        for i in range(1, 11):
            k = i / 10
            h.scene.robot = {"pos": [start[0] + (end[0] - start[0]) * k, start[1] + (end[1] - start[1]) * k],
                             "heading": -0.6, "seen": True}
            await asyncio.sleep(0.1)
        danger = await h.wait_for("world.event", lambda d: d.get("kind") == "danger_enter" and d["id"] == CRISPS,
                                  after=m, timeout=2.0)
        recoil = await h.wait_for("robot.cmd", lambda d: d.get("kind") == "recoil", after=m, timeout=REACT_WITHIN_S)
        warning = await h.wait_for("sfx.play", lambda d: d.get("sound") == "warning", after=m, timeout=REACT_WITHIN_S)
        red = await h.wait_for("robot.cmd", lambda d: d.get("kind") == "lights" and d.get("mode") == "flash"
                               and d.get("rgb") == [255, 0, 0], after=m, timeout=REACT_WITHIN_S)
        for msg in (recoil, warning, red):
            assert danger.t <= msg.t <= danger.t + REACT_WITHIN_S, msg
        assert recoil.data["ms"] == int(config.get("RECOIL_MS", 600))

        if check_serial:
            # the R packet reaches the robot's radio bridge
            deadline = asyncio.get_running_loop().time() + REACT_WITHIN_S
            while not [ln for _, ln in device.written[serial_mark:] if ln.startswith("R,")]:
                assert asyncio.get_running_loop().time() < deadline, f"no R packet; wrote {device.written[serial_mark:]}"
                await asyncio.sleep(0.01)
            r_lines = [ln for _, ln in device.written[serial_mark:] if ln.startswith("R,")]
            assert r_lines[0] == f"R,{recoil.data['ms']}"
            assert [ln for _, ln in device.written[serial_mark:] if ln.startswith("L,F,255,0,0")], "red flash not written"

        # and the narrator warns
        await h.wait_for("narration.say", lambda d: "Crisp Wyrm" in d["text"] and d["priority"] == 3,
                         after=m, timeout=1.0)

        # ---- the whole story, in order -----------------------------------------------------------------------
        order = [enter.t, added.t, danger.t, recoil.t]
        assert order == sorted(order), order
        h.assert_no_errors()


def test_hand_drop_threat_recoil():
    """Everything on the hub: giant, narration, from-sky threat, danger, recoil, warning, red light."""
    asyncio.run(run_big_moment(check_serial=False))


def test_recoil_reaches_serial_port():
    """The recoil and the red flash are written to the bridge micro:bit as R,<ms> and L,F,255,0,0,.. lines."""
    asyncio.run(run_big_moment(check_serial=True))
