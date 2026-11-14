import io
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.audio.capture import AudioInput, RingBuffer, read_wav, resample  # noqa: E402

RATE = 16000


def write_wav(path, x, rate=RATE, width=2):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


@pytest.fixture
def song(tmp_path):
    t = np.arange(8 * RATE) / RATE
    x = (0.5 * np.sin(2 * np.pi * 220 * t) * np.linspace(0.2, 1, len(t))).astype(np.float32)
    path = tmp_path / "song.wav"  # test fixture only; the module itself never writes audio
    write_wav(path, x)
    return path, np.round(x * 32767) / 32768


def test_file_mode_last_5s_matches_file(song):
    path, x = song
    audio = AudioInput({"AUDIO_RATE": RATE}, file=str(path), realtime=False).start()
    assert audio.wait(5)
    got = audio.last(5)
    assert len(got) == 5 * RATE
    np.testing.assert_allclose(got, x[-5 * RATE:], atol=1e-4)


def test_blocks_are_about_23ms_with_increasing_timestamps(song):
    path, x = song
    audio = AudioInput({"AUDIO_RATE": RATE}, file=str(path), realtime=False)
    blocks = []
    audio.on_block(lambda b, ts: blocks.append((len(b), ts, b.dtype)))
    audio.start().wait(5)
    sizes = [n for n, _, _ in blocks]
    assert sizes[0] == round(RATE * 0.023)
    assert sum(sizes) == len(x)
    assert all(d == np.float32 for _, _, d in blocks)
    ts = [t for _, t, _ in blocks]
    assert all(b > a for a, b in zip(ts, ts[1:]))


def test_realtime_file_mode_runs_at_real_speed(song):
    path, _ = song
    audio = AudioInput({"AUDIO_RATE": RATE}, file=str(path), realtime=True).start()
    time.sleep(0.5)
    audio.stop()
    n = len(audio.last(30))
    assert 0.3 * RATE < n < 0.8 * RATE


def test_file_resampled_to_pipeline_rate(tmp_path):
    x = np.sin(2 * np.pi * 440 * np.arange(22050) / 22050) * 0.5
    path = tmp_path / "a.wav"
    write_wav(path, x, rate=22050)
    audio = AudioInput({"AUDIO_RATE": 44100}, file=str(path), realtime=False).start()
    audio.wait(5)
    assert abs(len(audio.last(30)) - 44100) <= 1


def test_last_shorter_than_requested_when_buffer_not_full():
    audio = AudioInput({"AUDIO_RATE": RATE})
    audio.feed(np.ones(RATE, np.float32))
    assert len(audio.last(5)) == RATE


def test_ring_buffer_keeps_30s_and_wraps():
    r = RingBuffer(10)
    r.write(np.arange(7, dtype=np.float32))
    r.write(np.arange(7, 15, dtype=np.float32))
    np.testing.assert_array_equal(r.last(10), np.arange(5, 15))
    np.testing.assert_array_equal(r.last(3), [12, 13, 14])
    assert AudioInput({"AUDIO_RATE": RATE})._ring.size == 30 * RATE


def test_bad_callback_does_not_stop_others():
    audio = AudioInput({"AUDIO_RATE": RATE})
    seen = []
    audio.on_block(lambda b, ts: 1 / 0)
    audio.on_block(lambda b, ts: seen.append(len(b)))
    audio.feed(np.zeros(100, np.float32))
    assert seen == [100]


def test_device_parsing():
    assert AudioInput({"AUDIO_DEVICE": "3"}).device == 3
    assert AudioInput({"AUDIO_DEVICE": "USB Audio"}).device == "USB Audio"
    assert AudioInput({}).device is None


def test_never_writes_audio_to_disk(song, tmp_path, monkeypatch):
    path, _ = song
    before = set(os.listdir(tmp_path))
    monkeypatch.chdir(tmp_path)
    AudioInput({"AUDIO_RATE": RATE}, file=str(path), realtime=False).start().wait(5)
    assert set(os.listdir(tmp_path)) == before


def test_read_wav_24bit_and_stereo(tmp_path):
    x = np.array([0.5, -0.5, 0.25, 0.0])
    ints = (x * 8388607).astype(np.int32)
    raw = b"".join(int(v).to_bytes(3, "little", signed=True) * 2 for v in ints)  # stereo, L == R
    path = tmp_path / "s24.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(3)
        w.setframerate(8000)
        w.writeframes(raw)
    y, rate = read_wav(str(path))
    assert rate == 8000
    np.testing.assert_allclose(y, x, atol=1e-5)


def test_resample_identity_and_length():
    x = np.random.default_rng(0).standard_normal(1000).astype(np.float32)
    assert resample(x, 100, 100) is not None and len(resample(x, 100, 100)) == 1000
    assert len(resample(x, 100, 50)) == 500


def test_list_audio_devices_prints_indexes(capsys):
    sd = pytest.importorskip("sounddevice")
    sys.path.insert(0, str(ROOT / "scripts"))
    import list_audio_devices

    try:
        sd.query_devices()
    except Exception as e:  # no PortAudio backend on this machine
        pytest.skip(f"no audio backend: {e}")
    assert list_audio_devices.main(["--all"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].split()[0] == "idx"
