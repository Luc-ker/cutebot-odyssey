"""The independent two-board build needs only the laptop and phone, with no serial hardware."""
from scripts.launch import expected_health, page_urls, parse_args, plan_services


def test_default_launch_uses_phone_vision_without_serial_hardware():
    services = plan_services(parse_args([]), {"HUB_PORT": 8765})
    assert [name for name, _, _ in services] == ["hub", "brain", "vision"]
    assert services[1][1][-2:] == ["--skip", "bridge"]
    assert services[2][1][-2:] == ["-m", "vision"]  # no camera index: phone frames via hub
    assert expected_health([s[0] for s in services], live_vision=True) == {"hub": "hub", "brain": "brain"}


def test_bridge_requires_explicit_opt_in_and_old_skip_flag_still_works():
    enabled = plan_services(parse_args(["--bridge"]), {})
    assert "bridge" in [name for name, _, _ in enabled]
    assert expected_health([s[0] for s in enabled], live_vision=True)["serial_bridge"] == "bridge"
    skipped = plan_services(parse_args(["--no-bridge"]), {})
    assert "bridge" not in [name for name, _, _ in skipped]


def test_phone_and_eye_urls_share_https_origin():
    urls = page_urls({"HUB_PORT": 8765, "TLS_CERT": "cert.pem", "TLS_KEY": "key.pem"}, "192.168.1.2")
    assert urls["phone"] == "https://192.168.1.2:8765/phone/"
    assert urls["eye"] == "https://192.168.1.2:8765/eye/"


def test_replay_service_arguments_are_accepted(monkeypatch):
    import sys
    from scripts import vision_replay

    services = plan_services(parse_args(["--replay", "drive_around"]),
                             {"HUB_PORT": 8765, "TLS_CERT": "cert.pem", "TLS_KEY": "key.pem"})
    argv = next(argv for name, argv, _ in services if name == "vision")
    parsed = []

    async def capture(args):
        parsed.append(args)

    monkeypatch.setattr(sys, "argv", argv[1:])
    monkeypatch.setattr(vision_replay, "amain", capture)
    vision_replay.main()  # exercise the real CLI parser without starting a persistent service
    assert len(parsed) == 1 and not parsed[0].once
    assert parsed[0].source.endswith("drive_around.json")
    assert parsed[0].hub == "wss://127.0.0.1:8765/hub"


def test_no_music_launch_skips_audio_and_marks_fixed_world_mode():
    services = plan_services(parse_args(["--no-music"]), {})
    _, argv, env = next(service for service in services if service[0] == "brain")
    assert argv[-2:] == ["--skip", "bridge,audio"]
    assert env["GENRATOR_MUSIC_ENABLED"] == "false"
    assert "vision" in [name for name, _, _ in services]
