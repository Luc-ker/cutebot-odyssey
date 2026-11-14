import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.narration import triggers as tr  # noqa: E402
from server.narration.triggers import NarrationTriggers, load_templates  # noqa: E402


def world(wid, setting, name="The Drowned Kingdom", narration="The storm rolls in."):
    return {"id": wid,
            "world": {"name": name, "setting": setting, "mood": "", "time_of_day": "", "weather": "",
                      "palette": ["blue", "grey", "gold"]},
            "roles": [], "terrain": {"open_space": "open sea", "under_table": "the deep"},
            "restyle_prompt": "", "narration": narration, "music_signature": {}}


OCEAN = world("w-00000001", "stormy open ocean")
ODD = world("w-00000002", "a land made of cheese", name="Fromagia", narration="")


def make(w=OCEAN):
    t = NarrationTriggers(load_templates())
    t.on_world_current({"world": w, "previous_id": None})
    return t


def one(says):
    assert len(says) == 1
    return says[0]


# ---- each event kind ------------------------------------------------------------------------

def test_world_changed_speaks_world_narration_priority_3():
    s = one(make().on_event({"kind": "world_changed", "world_id": OCEAN["id"], "returning": False}))
    assert s["text"] == "The storm rolls in."
    assert s["priority"] == 3


def test_returning_world_gets_prefix():
    s = one(make().on_event({"kind": "world_changed", "world_id": OCEAN["id"], "returning": True}))
    assert s["text"] == "You return to The Drowned Kingdom. The storm rolls in."
    assert s["priority"] == 3


def test_world_changed_before_world_current_waits_for_it():
    t = make()
    new = world("w-00000009", "snowy night village", name="Frostholm", narration="Snow falls softly.")
    assert t.on_event({"kind": "world_changed", "world_id": new["id"], "returning": False}, now=1.0) == []
    s = one(t.on_world_current({"world": new, "previous_id": OCEAN["id"]}, now=1.5))
    assert s["text"] == "Snow falls softly."
    assert t.on_world_current({"world": new, "previous_id": None}, now=6.5) == []  # periodic resend: silent


def test_periodic_world_current_alone_says_nothing():
    t = make()
    assert t.on_world_current({"world": OCEAN, "previous_id": None}) == []


def test_object_added_uses_announce_priority_2():
    s = one(make().on_event({"kind": "object_added", "id": 4, "role": "sea_serpent", "name": "the Coil",
                             "behaviour": "threat", "announce": "A sea serpent rises from the deep.",
                             "from_sky": False}))
    assert s == {"text": "A sea serpent rises from the deep.", "priority": 2, "voice": "old"}


def test_object_added_without_announce_uses_setting_template():
    s = one(make().on_event({"kind": "object_added", "id": 4, "role": "ship", "name": "the Gull",
                             "announce": "", "from_sky": False}))
    assert s["text"] == "The Gull rises from the waves."
    assert s["priority"] == 2


def test_object_added_from_sky_and_nameless():
    s = one(make(ODD).on_event({"kind": "object_added", "id": 5, "role": "sea_serpent", "name": "",
                                "announce": "", "from_sky": True}))
    assert s["text"] == "The sea serpent falls from the sky!"


def test_giant_enter_per_setting_priority_2():
    s = one(make().on_event({"kind": "giant_enter", "id": "g1", "edge": "top"}))
    assert s["text"] == "A sea god's hand breaks the waves!"
    assert s["priority"] == 2


def test_danger_enter_priority_3():
    s = one(make().on_event({"kind": "danger_enter", "id": 4, "name": "the Coil", "role": "sea_serpent"}))
    assert s["text"] == "Beware! The Coil stirs."
    assert s["priority"] == 3


def test_blocked_priority_1():
    s = one(make(ODD).on_event({"kind": "blocked", "obstacle": "a wall of rock"}))
    assert s["text"] == "A wall of rock bars your way."
    assert s["priority"] == 1


def test_other_event_kinds_are_silent():
    t = make()
    for kind in ("object_removed", "giant_leave", "danger_exit", "horn", "shout", "friendly_enter"):
        assert t.on_event({"kind": kind}) == []


# ---- templates ------------------------------------------------------------------------------

def test_unknown_setting_uses_default_template():
    t = make(ODD)
    assert one(t.on_event({"kind": "giant_enter", "id": "g1"}))["text"] == \
        "A giant's hand reaches down from the sky!"
    s = one(t.on_event({"kind": "world_changed", "world_id": ODD["id"], "returning": False}))
    assert s["text"] == "You arrive in Fromagia."
    assert "voice" not in s


def test_setting_keyword_picks_template_and_voice():
    t = make(world("w-0000000a", "volcanic wasteland"))
    s = one(t.on_event({"kind": "giant_enter", "id": "g1"}))
    assert "fire giant" in s["text"]
    assert s["voice"] == "deep"


def test_setting_checked_before_name():
    # Name says "Kingdom", setting says ocean: the ocean template wins.
    s = one(make().on_event({"kind": "giant_enter", "id": "g1"}))
    assert "sea god" in s["text"]


def test_missing_templates_file_falls_back(tmp_path):
    t = NarrationTriggers(load_templates(tmp_path / "nope.json"))
    t.on_world_current({"world": OCEAN})
    assert one(t.on_event({"kind": "blocked", "obstacle": "reef"}))["text"] == "Reef bars your way."


def test_every_setting_has_match_keywords():
    data = load_templates()
    assert len(data["settings"]) == 8
    for entry in data["settings"]:
        assert entry["match"], entry["key"]


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


def test_run_publishes_narration_say():
    async def scenario():
        hub = FakeHub()
        await tr.run(hub, {})
        await hub.emit("world.current", {"world": OCEAN, "previous_id": None})
        await hub.emit("world.event", {"kind": "danger_enter", "id": 4, "name": "the Coil", "role": "sea_serpent"})
        assert hub.published == [("narration.say",
                                  {"text": "Beware! The Coil stirs.", "priority": 3, "voice": "old"})]

    asyncio.run(scenario())
