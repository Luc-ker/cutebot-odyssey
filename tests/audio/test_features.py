import asyncio
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.audio import features as F  # noqa: E402
from server.audio.features import AudioFeatures, brightness_from_centroid  # noqa: E402

RATE = 22050
rng = np.random.default_rng(7)


def feed(sig, rate=RATE, block=512):
    f = AudioFeatures(rate)
    out = []
    for i in range(0, len(sig), block):
        chunk = sig[i:i + block]
        out += f.process(chunk, (i + len(chunk)) / rate)  # ts = time of the chunk's last sample
    return out


def sine(freq, secs, amp=0.5):
    t = np.arange(int(secs * RATE)) / RATE
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def noise(secs, amp=0.3):
    return (amp * rng.standard_normal(int(secs * RATE))).astype(np.float32)


def test_white_noise_brighter_than_100hz_sine():
    n = np.mean([f["brightness"] for f in feed(noise(2))[5:]])
    s = np.mean([f["brightness"] for f in feed(sine(100, 2))[5:]])
    assert n > 0.8
    assert s < 0.15
    assert n > s


def test_louder_signal_gives_higher_energy():
    quiet_then_loud = np.concatenate([sine(440, 3, amp=0.5), sine(440, 1, amp=0.1), sine(440, 1, amp=0.5)])
    frames = feed(quiet_then_loud)
    quiet = np.mean([f["energy"] for f in frames[62:78]])
    loud = np.mean([f["energy"] for f in frames[82:98]])
    assert loud > quiet
    assert loud > 0.9 and quiet < 0.35


def test_energy_independent_of_playback_level():
    hi = np.mean([f["energy"] for f in feed(sine(440, 2, amp=0.6))[10:]])
    lo = np.mean([f["energy"] for f in feed(sine(440, 2, amp=0.06))[10:]])
    assert abs(hi - lo) < 0.05


def test_rate_is_20hz_and_fields_match_contract():
    frames = feed(noise(2))
    assert len(frames) == 40
    assert set(frames[0]) - {"_ts"} == {"rms", "energy", "brightness", "silent"}
    for f in frames:
        assert 0 <= f["energy"] <= 1 and 0 <= f["brightness"] <= 1
    ts = [f["_ts"] for f in frames]
    assert np.allclose(np.diff(ts), 0.05, atol=1e-3)  # hop is a whole number of samples


def test_silent_from_gate():
    # silent = 1.5 s gate hysteresis + up to 0.5 s for the gate's RMS window to empty
    frames = feed(np.concatenate([sine(440, 2), np.zeros(int(2.5 * RATE), np.float32)]))
    assert frames[30]["silent"] is False
    assert frames[-1]["silent"] is True


def test_brightness_scale_endpoints():
    assert brightness_from_centroid(0) == 0
    assert brightness_from_centroid(150) == 0
    assert brightness_from_centroid(8000) == 1
    assert 0.4 < brightness_from_centroid(1100) < 0.6


def test_run_publishes_audio_features():
    class FakeAudio:
        rate = RATE

        def on_block(self, cb):
            self.cb = cb

    class FakeHub:
        def __init__(self):
            self.published = []

        def sub(self, p, cb):
            pass

        async def pub(self, topic, data):
            self.published.append((topic, data))

    async def scenario():
        hub, audio = FakeHub(), FakeAudio()
        task = asyncio.create_task(F.run(hub, {}, audio=audio))
        await asyncio.sleep(0)
        audio.cb(noise(0.5), 0.5)
        await asyncio.sleep(0.05)
        task.cancel()
        return hub.published

    pubs = asyncio.run(scenario())
    assert len(pubs) == 10
    assert all(t == "audio.features" and "_ts" not in d for t, d in pubs)
