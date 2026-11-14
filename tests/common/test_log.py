import json
import logging

import pytest

from server.common import log as logmod
from server.common.log import get_logger, sanitise, trace


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("GENRATOR_LOG_DIR", str(tmp_path))
    monkeypatch.delenv("GENRATOR_LOG_LEVEL", raising=False)
    logmod._reset_for_tests()
    yield tmp_path
    logmod._reset_for_tests()


def lines(path):
    return [json.loads(l) for l in path.read_text().splitlines()]


def test_trace_writes_one_line_with_ms(isolated, capsys):
    with trace("gemini.compose", model="flash"):
        pass
    out = lines(isolated / "gemini.jsonl")
    assert len(out) == 1
    rec = out[0]
    assert rec["msg"] == "gemini.compose" and rec["service"] == "gemini" and rec["level"] == "INFO"
    assert rec["ms"] >= 0 and rec["end"] >= rec["start"]
    assert rec["model"] == "flash"
    assert "gemini.compose" in capsys.readouterr().err  # also on stderr


def test_bytes_field_logged_as_size(isolated):
    log = get_logger("audio")
    log.info("clip ready", clip=b"\x00" * 1234, nested={"img": bytearray(10)}, frames=[b"ab"])
    rec = lines(isolated / "audio.jsonl")[0]
    assert rec["clip"] == "<1234 bytes>"
    assert rec["nested"]["img"] == "<10 bytes>"
    assert rec["frames"] == ["<2 bytes>"]
    assert "\\u0000" not in (isolated / "audio.jsonl").read_text()


def test_array_like_logged_as_shape():
    class FakeArray:
        shape = (480, 640, 3)
        dtype = "uint8"

    assert sanitise(FakeArray()) == "<array shape=(480, 640, 3) dtype=uint8>"


def test_json_line_fields(isolated):
    get_logger("hub").warning("slow client", queue=40)
    rec = lines(isolated / "hub.jsonl")[0]
    assert set(rec) >= {"ts", "service", "level", "msg", "queue"}
    assert rec["level"] == "WARNING" and rec["queue"] == 40 and isinstance(rec["ts"], float)


def test_level_from_env(isolated, monkeypatch):
    monkeypatch.setenv("GENRATOR_LOG_LEVEL", "WARNING")
    log = get_logger("quiet")
    log.info("hidden")
    log.debug("hidden")
    log.warning("shown")
    assert [r["msg"] for r in lines(isolated / "quiet.jsonl")] == ["shown"]


def test_trace_records_error_and_reraises(isolated):
    log = get_logger("world")
    with pytest.raises(ValueError):
        with log.trace("world.compose") as extra:
            extra["world_id"] = "w-1"
            raise ValueError("bad")
    rec = lines(isolated / "world.jsonl")[0]
    assert rec["level"] == "ERROR" and rec["error"] == "ValueError: bad"
    assert rec["world_id"] == "w-1" and rec["ms"] >= 0


def test_does_not_leak_into_root_logger(isolated, caplog):
    with caplog.at_level(logging.DEBUG):
        get_logger("x").info("private")
    assert not any(r.getMessage() == "private" for r in caplog.records)


def test_logs_folder_is_git_ignored():
    gitignore = (logmod.REPO_ROOT / ".gitignore").read_text().split()
    assert "logs/" in gitignore
