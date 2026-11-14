import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.narration import shout as sh  # noqa: E402
from server.narration.shout import Shout, describe_open_space  # noqa: E402

OCEAN = {"id": "w-00000001",
         "world": {"name": "The Drowned Kingdom", "setting": "stormy open ocean"},
         "roles": [{"object_id": 9, "role": "lighthouse", "name": "the Old Lamp", "behaviour": "friendly"}],
         "terrain": {"open_space": "open sea", "under_table": "the deep"}}

OBJECTS = {"world_id": OCEAN["id"],
           "objects": [{"id": 4, "cls": "scissors", "role": "sea_serpent", "name": "the Coil",
                        "behaviour": "threat"},
                       {"id": 7, "cls": "chair", "role": "ship", "name": "the Gull", "behaviour": "neutral"},
                       {"id": 8, "cls": "cup", "role": "island", "name": "", "behaviour": "friendly"}],
           "clusters": [], "terrain": {"open_space": "open sea"}}


def make(facing=None):
    s = Shout()
    s.on_world_current({"world": OCEAN, "previous_id": None})
    s.on_world_objects(OBJECTS)
    s.on_robot_state({"pos": [0.5, 0.5], "heading": 0, "seen": True, "facing_id": facing})
    return s


def say_text(msgs):
    return next(d for t, d in msgs if t == "narration.say")["text"]


# ---- acceptance -----------------------------------------------------------------------------

def test_facing_threat_names_it_and_warns():
    text = say_text(make(facing=4).press(0.0))
    assert text == "Ahead stands the Coil, a sea serpent. It looks dangerous."


def test_facing_nothing_describes_terrain():
    assert say_text(make(facing=None).press(0.0)) == "Only open sea lies ahead."


# ---- details --------------------------------------------------------------------------------

def test_facing_neutral_has_no_warning():
    assert say_text(make(facing=7).press(0.0)) == "Ahead stands the Gull, a ship."


def test_nameless_object_uses_role_with_article():
    assert say_text(make(facing=8).press(0.0)) == "Ahead stands an island."


def test_object_known_only_from_world_roles():
    assert say_text(make(facing=9).press(0.0)) == "Ahead stands the Old Lamp, a lighthouse."


def test_unknown_facing_id():
    assert "shrouded" in say_text(make(facing=99).press(0.0))


def test_terrain_from_world_when_objects_have_none():
    s = Shout()
    s.on_world_current({"world": OCEAN})
    assert say_text(s.press(0.0)) == "Only open sea lies ahead."


def test_no_world_at_all():
    assert say_text(Shout().press(0.0)) == "Only open land lies ahead."


def test_open_space_article_stripped():
    assert describe_open_space("the frozen tundra") == "Only frozen tundra lies ahead."


def test_publishes_world_event_and_priority():
    msgs = make(facing=4).press(0.0)
    assert ("world.event", {"kind": "shout", "facing_id": 4}) in msgs
    assert next(d for t, d in msgs if t == "narration.say")["priority"] == 2


def test_cooldown_1_5s():
    s = make()
    assert s.press(10.0)
    assert s.press(11.0) == []
    assert s.press(11.6)


def test_world_change_drops_old_terrain():
    s = make()
    snow = {**OCEAN, "id": "w-00000002", "terrain": {"open_space": "snowfield"}, "roles": []}
    s.on_world_current({"world": snow})
    assert say_text(s.press(0.0)) == "Only snowfield lies ahead."


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


def test_run_only_reacts_to_shout_button():
    async def scenario():
        hub = FakeHub()
        await sh.run(hub, {})
        await hub.emit("world.current", {"world": OCEAN})
        await hub.emit("gamepad.button", {"button": "horn"})
        assert hub.published == []
        await hub.emit("gamepad.button", {"button": "shout"})
        assert [t for t, _ in hub.published] == ["narration.say", "world.event"]

    asyncio.run(scenario())
