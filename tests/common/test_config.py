import json

import pytest

from server.common.config import CONFIG_PATH, load_config

C10_KEYS = """HUB_PORT TLS_CERT TLS_KEY RADIO_GROUP RADIO_CHANNEL DRIVE_HZ FAILSAFE_MS SAFETY_STOP_CM RECOIL_MS
TABLE_W_CM TABLE_H_CM VISION_HZ JETSON_HOST JETSON_HTTP_PORT OBJECT_GRACE_S CLUSTER_GAP
DANGER_RADIUS FRIENDLY_RADIUS FACING_HALF_ANGLE_DEG FACING_MAX_DIST AUDIO_DEVICE AUDIO_RATE
CLIP_SECONDS GEMINI_INTERVAL_S GEMINI_TIMEOUT_S GEMINI_MODEL WORLD_CHANGE_THRESHOLD
RETURN_MATCH_THRESHOLD NARRATION_MAX_CHARS TRANSITION_MS LIGHT_MAX_HZ""".split()


def test_every_c10_key_present_and_documented():
    raw = json.loads(CONFIG_PATH.read_text())
    cfg = load_config(env={})
    for key in C10_KEYS:
        assert key in cfg, key
        assert raw["_doc"].get(key), f"{key} has no _doc line"
    assert "_doc" not in cfg


def test_no_secrets_in_file():
    cfg = load_config(env={})
    assert not any("API_KEY" in k for k in cfg)


def test_env_override_casts_to_int():
    cfg = load_config(env={"GENRATOR_HUB_PORT": "9000"})
    assert cfg["HUB_PORT"] == 9000
    assert isinstance(cfg["HUB_PORT"], int)


def test_env_override_casts_float_and_str():
    cfg = load_config(env={"GENRATOR_CLIP_SECONDS": "5", "GENRATOR_GEMINI_MODEL": "x"})
    assert cfg["CLIP_SECONDS"] == 5.0 and isinstance(cfg["CLIP_SECONDS"], float)
    assert cfg["GEMINI_MODEL"] == "x"


def test_real_environment_is_used(monkeypatch):
    monkeypatch.setenv("GENRATOR_HUB_PORT", "9000")
    assert load_config()["HUB_PORT"] == 9000


def test_bad_cast_raises_clear_error():
    with pytest.raises(ValueError, match="GENRATOR_HUB_PORT"):
        load_config(env={"GENRATOR_HUB_PORT": "abc"})
