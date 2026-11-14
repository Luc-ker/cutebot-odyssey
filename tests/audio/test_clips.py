import io
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.audio.clips import ClipStore, make_clip, resample_fft  # noqa: E402

rng = np.random.default_rng(5)


class FakeAudio:
    def __init__(self, x, rate):
        self.x, self.rate = np.asarray(x, np.float32), rate

    def last(self, seconds):
        return self.x[-int(round(seconds * self.rate)):]


def music(secs, rate=44100, amp=0.3):
    t = np.arange(int(secs * rate)) / rate
    return (amp * (np.sin(2 * np.pi * 220 * t) + 0.5 * np.sin(2 * np.pi * 330 * t))
            * (0.7 + 0.3 * np.sin(2 * np.pi * 2 * t))).astype(np.float32)


def parse(b):
    with wave.open(io.BytesIO(b)) as w:
        return w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()


@pytest.mark.parametrize("rate", [44100, 48000, 22050, 16000])
def test_returns_16k_mono_wav_of_right_length(rate):
    store = ClipStore(FakeAudio(music(12, rate), rate))
    clip = store.get_clip(8)
    sr, ch, width, frames = parse(clip)
    assert (sr, ch, width) == (16000, 1, 2)
    assert abs(frames / 16000 - 8) <= 0.1


def test_silent_buffer_returns_none():
    assert ClipStore(FakeAudio(np.zeros(10 * 44100), 44100)).get_clip(8) is None
    room = 0.001 * rng.standard_normal(10 * 44100)
    assert ClipStore(FakeAudio(room, 44100)).get_clip(8) is None


def test_mostly_silent_returns_none_but_30pct_music_is_kept():
    rate = 16000
    quiet = np.zeros(int(5.8 * rate), np.float32)
    assert make_clip(np.concatenate([quiet, music(2.2, rate)]), rate) is None   # 72.5 % silent
    clip = make_clip(np.concatenate([quiet[: int(5.2 * rate)], music(2.8, rate)]), rate)  # 65 % silent
    assert clip is not None


def test_leading_and_trailing_silence_trimmed():
    rate = 16000
    x = np.concatenate([np.zeros(rate), music(5, rate), np.zeros(rate)])
    _, _, _, frames = parse(make_clip(x, rate))
    assert abs(frames / 16000 - 5) <= 0.05


def test_peak_normalised():
    rate = 16000
    clip = make_clip(music(6, rate, amp=0.02), rate)
    with wave.open(io.BytesIO(clip)) as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), "<i2")
    assert 0.9 < np.abs(pcm).max() / 32767 <= 0.951


def test_resample_removes_content_above_new_nyquist():
    rate = 48000
    t = np.arange(rate) / rate
    x = np.sin(2 * np.pi * 1000 * t) + np.sin(2 * np.pi * 12000 * t)  # 12 kHz would alias at 16 kHz
    y = resample_fft(x, rate, 16000)
    spec = np.abs(np.fft.rfft(y)) / len(y)
    freqs = np.fft.rfftfreq(len(y), 1 / 16000)
    assert spec[np.argmin(np.abs(freqs - 1000))] > 0.4
    assert spec[np.argmin(np.abs(freqs - 4000))] < 0.01  # where 12 kHz would fold to


def test_too_short_returns_none():
    assert make_clip(music(0.2, 16000), 16000) is None
