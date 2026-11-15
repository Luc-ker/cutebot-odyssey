import copy
import json

import pytest

from server.common.schemas import SCHEMA_DIR, check_envelope, known_topics, validate_envelope

DOC = json.loads((SCHEMA_DIR / "topics.schema.json").read_text())
SAMPLES = DOC["_samples"]

C3_TOPICS = """vision.state camera.frame robot.telemetry robot.cmd gamepad.button audio.beat audio.features world.current
world.transition world.objects robot.state world.event narration.say narration.speak narration.done sfx.play
video.prompt video.status webrtc.signal system.health system.reset world.select world.composing show.set show.state""".split()


def test_every_c3_topic_has_a_schema_and_a_sample():
    assert sorted(C3_TOPICS) == known_topics()
    assert sorted(s["topic"] for s in SAMPLES["valid"]) == sorted(C3_TOPICS)


@pytest.mark.parametrize("env", SAMPLES["valid"], ids=lambda e: e["topic"])
def test_valid_samples_pass(env):
    assert validate_envelope(env) == []


@pytest.mark.parametrize("case", SAMPLES["invalid"], ids=lambda c: c["why"])
def test_invalid_samples_fail(case):
    assert validate_envelope(case["env"]), case["why"]


def test_pos_outside_unit_square_rejected_with_path():
    env = copy.deepcopy(next(e for e in SAMPLES["valid"] if e["topic"] == "vision.state"))
    env["data"]["objects"][0]["pos"] = [2, 0]
    errors = validate_envelope(env)
    assert errors == ["data.objects[0].pos[0]: 2 is greater than the maximum of 1"]


def test_unknown_topic_is_a_warning_not_an_error():
    env = {"topic": "custom.thing", "ts": 1.0, "src": "x", "data": {"anything": 1}}
    warnings = []
    assert validate_envelope(env, warnings) == []
    assert len(warnings) == 1 and "custom.thing" in warnings[0]
    assert check_envelope(env) == ([], warnings)


def test_world_event_kind_specific_fields():
    env = {"topic": "world.event", "ts": 1.0, "src": "x", "data": {"kind": "danger_enter", "id": 9}}
    errors = validate_envelope(env)
    assert any("'name' is required" in e for e in errors)
    assert any("'role' is required" in e for e in errors)


def test_not_a_dict_does_not_crash():
    assert validate_envelope(None)
    assert validate_envelope([1, 2])
