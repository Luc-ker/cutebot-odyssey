"""T63 — gamepad reset and full demo reset."""
import asyncio
import importlib.util
from pathlib import Path

from server.world import reset as mod
from server.world.reset import ResetHandler, colour_for

WORLD = {"id": "w-0000beef", "world": {"name": "The Salt Sea", "setting": "open ocean",
                                      "palette": ["deep blue", "white", "gold"]},
         "narration": "The table floods; you sail the Salt Sea."}
COLOURS = {"blue": [0, 80, 255], "white": [255, 255, 255]}


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


def test_gamepad_reset_one_narration_with_world_line():
    async def main():
        hub = FakeHub()
        handler = await mod.run(hub, {})
        handler.colours = COLOURS
        await hub.pub("world.current", {"world": WORLD, "previous_id": None})
        await hub.pub("gamepad.button", {"button": "horn"})
        await hub.pub("gamepad.button", {"button": "reset"})
        says = [d for t, d in hub.published if t == "narration.say"]
        assert says == [{"text": WORLD["narration"], "priority": 2}]
        cmds = [d for t, d in hub.published if t == "robot.cmd"]
        assert cmds == [{"kind": "lights", "mode": "solid", "rgb": [0, 80, 255], "ms": 0}]

    asyncio.run(main())


def test_colour_words():
    assert colour_for("deep blue", COLOURS) == [0, 80, 255]
    assert colour_for("ultraviolet", COLOURS) == [255, 255, 255]


def test_no_world_still_sets_lights():
    out = ResetHandler(COLOURS).on_button({"button": "reset"})
    assert [t for t, _ in out] == ["robot.cmd"]


def _load_script():
    path = Path(__file__).resolve().parents[2] / "scripts" / "reset_demo.py"
    spec = importlib.util.spec_from_file_location("reset_demo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_publishes_reset_then_world_select():
    script = _load_script()

    async def main():
        hub = FakeHub()
        await mod.run(hub, {})            # the brain's reset module, listening
        await script.reset_demo(hub)       # what the script sends
        topics = [t for t, _ in hub.published]
        assert topics == ["system.reset", "world.select"]
        assert hub.published[1][1] == {"name": "kingdom"}

    asyncio.run(main())


def test_script_default_url():
    script = _load_script()
    assert script.default_url({"HUB_PORT": 9000}) == "ws://localhost:9000/hub"
    assert script.default_url({"HUB_PORT": 9000, "TLS_CERT": "c.pem"}) == "wss://localhost:9000/hub"
