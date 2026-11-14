import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.world import prompt_composer as pc  # noqa: E402
from server.world.prompt_composer import PromptComposer, compose, giant_phrase  # noqa: E402

VOCAB = {"castle": "a stone castle tower", "ship": "a wooden sailing ship", "sea_serpent": "a coiling sea serpent"}

KINGDOM = {
    "id": "w-00000001",
    "world": {"name": "The Amber Realm", "setting": "medieval kingdom", "mood": "heroic",
              "time_of_day": "noon", "weather": "clear", "palette": ["gold", "green", "stone grey"]},
    "roles": [{"object_id": 3, "role": "castle", "name": "Highkeep", "behaviour": "neutral"}],
    "terrain": {"open_space": "meadow", "under_table": "the underworld"},
    "restyle_prompt": "a sunny medieval kingdom, rolling hills, painterly",
    "narration": "", "music_signature": {},
}
OCEAN = {**KINGDOM, "id": "w-00000002",
         "world": {**KINGDOM["world"], "setting": "stormy open ocean"},
         "restyle_prompt": "a stormy ocean at dusk, rain, lantern light"}


# ---- pure compose -------------------------------------------------------------------

def test_facing_castle_in_kingdom_mentions_stone_castle():
    text = compose(KINGDOM, "castle", False, VOCAB)
    assert "stone castle" in text
    assert text.startswith("a sunny medieval kingdom")
    assert "in the foreground" in text
    assert text.endswith(pc.TAIL)


def test_no_facing_no_giant_is_base_plus_tail():
    assert compose(KINGDOM, None, False, VOCAB) == f"{KINGDOM['restyle_prompt']}, {pc.TAIL}"


def test_giant_phrase_suits_setting():
    assert "sea god" in compose(OCEAN, None, True, VOCAB)
    assert "stone titan" in giant_phrase(KINGDOM)
    snow = {"world": {"setting": "snowy night forest"}}
    assert "frost giant" in giant_phrase(snow)
    assert giant_phrase(None) == pc._DEFAULT_GIANT


def test_unknown_role_falls_back_to_role_name():
    assert "lava beast in the foreground" in compose(KINGDOM, "lava_beast", False, VOCAB)


def test_capped_at_400_and_keeps_facing_and_tail():
    long_world = {**KINGDOM, "restyle_prompt": "word " * 200}
    text = compose(long_world, "castle", True, VOCAB)
    assert len(text) <= 400
    assert "stone castle" in text and text.endswith(pc.TAIL)


def test_no_world_base_still_returns_text():
    assert compose(None, None, False, VOCAB) == pc.TAIL


# ---- stateful composer ------------------------------------------------------------

def make(world=KINGDOM):
    c = PromptComposer(VOCAB)
    c.on_world_current({"world": world, "previous_id": None})
    c.on_world_objects({"world_id": world["id"], "objects": [{"id": 3, "role": "castle", "name": "Highkeep"}]})
    return c


def test_identical_inputs_twice_publish_once():
    c = make()
    assert c.tick(100.0) is not None
    c.on_robot_state({"facing_id": None})
    c.on_world_current({"world": KINGDOM, "previous_id": None})  # periodic resend, same world
    assert c.tick(101.0) is None
    assert c.tick(102.0) is None


def test_facing_change_publishes_new_prompt():
    c = make()
    c.tick(100.0)
    c.on_robot_state({"facing_id": 3})
    text = c.tick(101.0)
    assert text and "stone castle" in text


def test_rate_limited_to_two_per_second():
    c = make()
    assert c.tick(100.0) is not None
    c.on_robot_state({"facing_id": 3})
    assert c.tick(100.2) is None  # too soon
    assert c.tick(100.5) is not None  # goes out once the interval passes


def test_giant_enter_and_leave():
    c = make()
    c.tick(100.0)
    c.on_world_event({"kind": "giant_enter", "id": "g1", "edge": "top"})
    assert "stone titan" in c.tick(101.0)
    c.on_world_event({"kind": "giant_leave", "id": "g1"})
    assert "titan" not in c.tick(102.0)


def test_silent_during_transition_then_resumes():
    c = make()
    c.tick(100.0)
    c.on_transition({"from": KINGDOM, "to": OCEAN, "started": 101.0, "duration_ms": 3000}, now=101.0)
    assert c.tick(101.5) is None
    assert c.tick(103.9) is None
    text = c.tick(104.1)
    assert text and text.startswith("a stormy ocean")


def test_stale_world_objects_ignored():
    c = make()
    c.on_world_objects({"world_id": "w-old", "objects": [{"id": 3, "role": "ship"}]})
    c.on_robot_state({"facing_id": 3})
    assert "stone castle" in c.tick(100.0)


def test_reset_clears_everything():
    c = make()
    c.tick(100.0)
    c.reset()
    assert c.tick(101.0) is None


def test_run_publishes_over_fake_hub():
    class FakeHub:
        def __init__(self):
            self.subs, self.published = {}, []

        def sub(self, pattern, cb):
            self.subs[pattern] = cb

        async def pub(self, topic, data):
            self.published.append((topic, data))

    async def scenario():
        hub = FakeHub()
        task = asyncio.create_task(pc.run(hub, {}))
        await asyncio.sleep(0)
        await hub.subs["world.current"]({"data": {"world": KINGDOM, "previous_id": None}})
        await asyncio.sleep(0.25)
        task.cancel()
        return hub.published

    published = asyncio.run(scenario())
    assert published == [("video.prompt", {"prompt": compose(KINGDOM, None, False, pc.load_vocab())})]
