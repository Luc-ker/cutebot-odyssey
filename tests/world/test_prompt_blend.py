import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.world import prompt_blend as pb  # noqa: E402
from server.world.prompt_blend import PromptBlender, blend_steps, short_desc  # noqa: E402


def world(wid, setting, tod, prompt):
    return {"id": wid, "world": {"name": wid, "setting": setting, "time_of_day": tod},
            "restyle_prompt": prompt}


OCEAN = world("w-1", "stormy ocean", "dusk", "stormy ocean at dusk, rain, wooden ships")
VOLCANO = world("w-2", "volcanic wasteland", "", "a volcanic wasteland, rivers of lava, ash sky")
SNOW = world("w-3", "snowy forest", "night", "a snowy forest at night, moonlight, pines")


def run_transition(blender, frm, to, started, duration_ms, until, step=0.05):
    blender.start({"from": frm, "to": to, "started": started, "duration_ms": duration_ms}, now=started)
    out, t = [], started
    while t <= until + 1e-9:
        out += blender.tick(t)
        t += step
    return out


def test_short_desc_uses_setting_and_time():
    assert short_desc(OCEAN) == "stormy ocean at dusk"
    assert short_desc(VOLCANO) == "volcanic wasteland"
    assert short_desc({"restyle_prompt": "a meadow, flowers"}) == "a meadow"


def test_steps_mix_old_into_new():
    steps = blend_steps("A", "B", "stormy ocean at dusk", "volcanic wasteland")
    assert steps[0] == "A" and steps[-1] == "B"
    assert any("stormy ocean at dusk turning into volcanic wasteland" in s for s in steps)


def test_3000ms_transition_gives_4_to_6_prompts_ending_on_new():
    b = PromptBlender()
    b.on_video_prompt({"prompt": OCEAN["restyle_prompt"]})
    out = run_transition(b, OCEAN, VOLCANO, started=100.0, duration_ms=3000, until=103.0)
    assert 4 <= len(out) <= 6
    assert out[0] == OCEAN["restyle_prompt"]
    assert out[-1] == VOLCANO["restyle_prompt"]
    assert len(out) == len(set(out))  # in order, no repeats


def test_all_prompts_land_inside_the_window():
    b = PromptBlender()
    out = run_transition(b, OCEAN, VOLCANO, started=100.0, duration_ms=3000, until=102.99)
    assert out[-1] == VOLCANO["restyle_prompt"]


def test_second_transition_mid_blend_starts_from_current_mixed_prompt():
    b = PromptBlender()
    b.on_video_prompt({"prompt": OCEAN["restyle_prompt"]})
    first = run_transition(b, OCEAN, VOLCANO, started=100.0, duration_ms=3000, until=101.3)
    current = first[-1]
    assert current not in (OCEAN["restyle_prompt"], VOLCANO["restyle_prompt"])  # really mid-blend

    second = run_transition(b, VOLCANO, SNOW, started=101.3, duration_ms=3000, until=104.3)
    assert second[0] == current
    assert second[-1] == SNOW["restyle_prompt"]
    assert any("volcanic wasteland turning into snowy forest at night" in s for s in second)
    # Mixing is from the in-flight target (volcano), so the original ocean drops out after step 1.
    assert not any("stormy ocean" in s for s in second[2:])


def test_without_seen_prompt_starts_from_old_world():
    b = PromptBlender()
    out = run_transition(b, OCEAN, VOLCANO, started=0.0, duration_ms=3000, until=3.0)
    assert out[0] == OCEAN["restyle_prompt"]


def test_prompts_capped():
    long = world("w-9", "x", "", "word " * 120)
    for s in blend_steps(long["restyle_prompt"], long["restyle_prompt"], "a", "b"):
        assert len(s) <= pb.MAX_CHARS


def test_reset_drops_schedule():
    b = PromptBlender()
    b.start({"from": OCEAN, "to": VOLCANO, "started": 0.0, "duration_ms": 3000}, now=0.0)
    b.reset()
    assert b.tick(5.0) == []


def test_run_publishes_sequence_over_fake_hub():
    class FakeHub:
        def __init__(self):
            self.subs, self.published = {}, []

        def sub(self, pattern, cb):
            self.subs[pattern] = cb

        async def pub(self, topic, data):
            self.published.append((topic, data))

    async def scenario():
        hub = FakeHub()
        task = asyncio.create_task(pb.run(hub, {}))
        await asyncio.sleep(0)
        import time
        await hub.subs["world.transition"]({"data": {"from": OCEAN, "to": VOLCANO,
                                                     "started": time.time(), "duration_ms": 300}})
        await asyncio.sleep(0.45)
        task.cancel()
        return hub.published

    published = asyncio.run(scenario())
    assert [t for t, _ in published] == ["video.prompt"] * len(published)
    assert published[-1][1]["prompt"] == VOLCANO["restyle_prompt"]
