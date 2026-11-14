import asyncio
import importlib.util
import json
import time
from pathlib import Path

import pytest

from server.common.schemas import validate_envelope

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("vision_replay", ROOT / "scripts" / "vision_replay.py")
vr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vr)

SCENES = sorted((ROOT / "scripts" / "scenes").glob("*.json"))


def env(data):
    return {"topic": "vision.state", "ts": time.time(), "src": "vision-replay", "data": data}


def test_five_scenes_exist():
    names = {p.stem for p in SCENES}
    assert {"static_view", "drive_around", "approach_threat", "hand_enters", "object_dropped"} <= names


@pytest.mark.parametrize("path", SCENES, ids=lambda p: p.stem)
def test_every_frame_of_every_scene_is_valid(path):
    frames, scene = vr.load_frames(path)
    assert len(frames) == round(scene["duration_s"] * scene["hz"])
    for t, data in frames:
        assert validate_envelope(env(data)) == [], (path.stem, t)


def test_replay_publishes_in_order_with_correct_spacing():
    frames, scene = vr.load_frames(ROOT / "scripts" / "scenes" / "drive_around.json")
    frames = frames[:15]  # 1.5 s at 10 Hz
    got = []

    async def publish(data):
        got.append((time.monotonic(), data))

    sent = asyncio.run(vr.replay(frames, publish, scene=scene))
    assert sent == 15 and len(got) == 15
    t0 = got[0][0]
    for i, (t, data) in enumerate(got):
        assert abs((t - t0) - frames[i][0]) < 0.02, (i, t - t0)
        assert validate_envelope(env(data)) == []
        assert data["objects"] == frames[i][1]["objects"]  # in order
    stamps = [d["frame_ts"] for _, d in got]
    assert stamps == sorted(stamps)


def test_objects_sweep_across_the_view_and_come_back_with_the_same_id():
    frames, _ = vr.load_frames("scenes/drive_around.json")  # resolves relative to scripts/
    by_t = {round(t, 1): d for t, d in frames}
    chair = lambda t: next((o for o in by_t[t]["objects"] if o["id"] == 1), None)  # noqa: E731
    assert chair(0.0)["pos"][0] > chair(4.0)["pos"][0]      # the robot turns right: the chair slides left
    assert chair(8.0) is None                                 # out of view
    assert chair(15.0) is not None                            # back again, same id
    bottle = {round(t, 1): o for t, d in frames for o in d["objects"] if o["id"] == 2}
    assert max(bottle[9.5]["size"]) > 3 * max(bottle[5.0]["size"])  # it grows as the robot drives up


def test_scene_semantics():
    frames, _ = vr.load_frames("object_dropped.json")
    by_t = dict(frames)
    assert all(o["id"] != 9 for o in by_t[4.0]["objects"])
    assert any(o["id"] == 9 and o["cls"] == "teddy bear" for o in by_t[6.0]["objects"])
    assert by_t[4.0]["giants"] and by_t[4.0]["giants"][0]["edge"] == "top"
    assert by_t[8.0]["giants"] == []
    hand = dict(vr.load_frames("hand_enters.json")[0])
    assert hand[4.5]["giants"][0]["kind"] == "hand" and hand[1.0]["giants"] == []


def test_recording_round_trip(tmp_path):
    frames, _ = vr.load_frames("static_view.json")
    rec = tmp_path / "run.jsonl"
    rec.write_text("".join(json.dumps({"t": t, "data": d}) + "\n" for t, d in frames[:5]))
    again, scene = vr.load_frames(rec)
    assert scene is None and again == frames[:5]


def test_pause_shifts_schedule_and_inject_adds_hand():
    frames, scene = vr.load_frames("static_view.json")
    frames = frames[:6]
    controls = vr.Controls()
    got = []

    async def publish(data):
        got.append((time.monotonic(), data))
        if len(got) == 2:
            controls.paused = True
            controls.inject_hand = True
            asyncio.get_running_loop().call_later(0.3, setattr, controls, "paused", False)

    asyncio.run(vr.replay(frames, publish, scene=scene, controls=controls))
    gap = got[2][0] - got[1][0]
    assert 0.35 < gap < 0.5           # 0.1 s spacing + 0.3 s pause
    assert got[3][0] - got[2][0] == pytest.approx(0.1, abs=0.02)
    assert got[1][1]["giants"] == [] and got[3][1]["giants"]  # the injected hand appears


def test_loop_continues_past_end():
    frames, scene = vr.load_frames("static_view.json")
    frames = frames[:3]
    controls = vr.Controls()
    got = []

    async def publish(data):
        got.append(data)
        if len(got) == 7:
            controls.quit = True

    asyncio.run(vr.replay(frames, publish, loop=True, speed=10, scene=scene, controls=controls))
    assert len(got) == 7
