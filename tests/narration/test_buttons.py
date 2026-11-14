import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.narration import buttons as bt  # noqa: E402
from server.narration.buttons import Buttons, horn_sound, nearest_setting  # noqa: E402


def world(setting, name="Somewhere"):
    return {"id": "w-00000001", "world": {"name": name, "setting": setting}}


def with_world(setting, name="Somewhere"):
    b = Buttons()
    b.on_world_current({"world": world(setting, name), "previous_id": None})
    return b


# ---- acceptance -----------------------------------------------------------------------------

def test_horn_in_stormy_open_ocean_is_horn_ocean():
    msgs = with_world("stormy open ocean", "The Drowned Kingdom").press("horn", 0.0)
    assert ("sfx.play", {"sound": "horn_ocean"}) in msgs
    assert ("world.event", {"kind": "horn"}) in msgs


def test_light_sends_one_flash_command():
    msgs = Buttons().press("light", 0.0)
    cmds = [d for t, d in msgs if t == "robot.cmd"]
    assert cmds == [{"kind": "lights", "mode": "flash", "rgb": [255, 214, 170], "ms": 600}]
    assert ("sfx.play", {"sound": "whoosh"}) in msgs


# ---- setting matching -----------------------------------------------------------------------

@pytest.mark.parametrize("setting,key", [
    ("stormy open ocean", "ocean"),
    ("volcanic wasteland", "wasteland"),
    ("snowy night village", "snow"),
    ("medieval kingdom", "kingdom"),
    ("neon city", "neon_city"),
    ("rainforest", "jungle"),
    ("royal court", "royal_court"),
    ("space station", "space_station"),
])
def test_eight_settings(setting, key):
    assert nearest_setting(world(setting)) == key


def test_unknown_setting_defaults_to_kingdom():
    assert horn_sound(world("a land made of cheese", "Fromagia")) == "horn_kingdom"
    assert horn_sound(None) == "horn_kingdom"


def test_name_used_when_setting_has_no_keyword():
    assert nearest_setting(world("a strange place", "The Frozen Wastes")) == "snow"


# ---- cooldowns ------------------------------------------------------------------------------

def test_cooldown_is_per_button():
    b = Buttons()
    assert b.press("horn", 0.0)
    assert b.press("horn", 0.3) == []
    assert b.press("light", 0.3)  # other button not blocked
    assert b.press("horn", 0.6)


def test_other_buttons_ignored():
    b = Buttons()
    assert b.press("shout", 0.0) == []
    assert b.press("reset", 0.0) == []
    assert b.press(None, 0.0) == []


# ---- hub wiring -----------------------------------------------------------------------------

class FakeHub:
    def __init__(self):
        self.subs, self.published = [], []

    def sub(self, pattern, cb):
        self.subs.append((pattern, cb))

    async def pub(self, topic, data):
        self.published.append((topic, data))

    async def emit(self, topic, data):
        for p, cb in self.subs:
            if p == topic:
                await cb({"topic": topic, "ts": 0, "src": "test", "data": data})


def test_run_wires_world_and_buttons():
    async def scenario():
        hub = FakeHub()
        await bt.run(hub, {})
        await hub.emit("world.current", {"world": world("volcanic wasteland")})
        await hub.emit("gamepad.button", {"button": "horn"})
        assert hub.published[0] == ("sfx.play", {"sound": "horn_wasteland"})

    asyncio.run(scenario())
