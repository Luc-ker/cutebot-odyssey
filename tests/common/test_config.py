import json

import pytest

from server.common.config import CONFIG_PATH, load_config

C10_KEYS = """HUB_PORT TLS_CERT TLS_KEY RADIO_GROUP RADIO_CHANNEL DRIVE_HZ FAILSAFE_MS SAFETY_STOP_CM RECOIL_MS
VISION_HZ VISION_HOST VISION_HTTP_PORT FRAME_WIDTH CAMERA_HFOV_DEG VIEW_GRACE_S OBJECT_FORGET_S CLUSTER_GAP
DANGER_SIZE FRIENDLY_SIZE NEAR_CM FACING_HALF_ANGLE_DEG FACING_MIN_SIZE AUDIO_DEVICE AUDIO_RATE
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


@pytest.mark.parametrize("existing_key", [None, "key-from-shell"])
def test_repo_dotenv_loads_key_without_overriding_shell_or_exposing_it_in_config(tmp_path, monkeypatch, existing_key):
    from server.common import config

    env_file = tmp_path / ".env"
    env_file.write_text('GEMINI_API_KEY="key-from-local-file"\nGENRATOR_HUB_PORT=9876\n')
    monkeypatch.setattr(config, "ENV_PATH", env_file)
    monkeypatch.delenv("GENRATOR_HUB_PORT", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    if existing_key is not None:
        monkeypatch.setenv("GEMINI_API_KEY", existing_key)
    cfg = config.load_config()
    import os
    assert os.environ["GEMINI_API_KEY"] == (existing_key or "key-from-local-file")
    assert cfg["HUB_PORT"] == 9876
    assert "GEMINI_API_KEY" not in cfg
    assert config.load_config(env={})["HUB_PORT"] == 8765
