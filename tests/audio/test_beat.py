import sys
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.audio.beat import BeatTracker, estimate_tempo  # noqa: E402

RATE = 44100
BLOCK = 1024  # ~23 ms, like AudioInput


def click_track(bpm, secs, rate=RATE, start=0.1, amp=0.8, jitter_ms=0.0, seed=0):
    rng = np.random.default_rng(seed)
    x = np.zeros(int(secs * rate), np.float32)
    click = (amp * np.sin(2 * np.pi * 1500 * np.arange(int(0.02 * rate)) / rate)
             * np.exp(-np.arange(int(0.02 * rate)) / (0.004 * rate))).astype(np.float32)
    times = []
    t = start
    while t < secs - 0.03:
        tj = t + rng.uniform(-jitter_ms, jitter_ms) / 1000
        i = int(tj * rate)
        x[i:i + len(click)] += click[: len(x) - i]
        times.append(tj)
        t += 60.0 / bpm
    return x + 0.001 * rng.standard_normal(len(x)).astype(np.float32), times


def run(tracker, x, rate=RATE, block=BLOCK, t0=1000.0):
    beats = []
    for i in range(0, len(x), block):
        chunk = x[i:i + block]
        beats += tracker.process(chunk, t0 + (i + len(chunk)) / rate)
    return beats


def test_120bpm_click_tempo_and_count():
    x, clicks = click_track(120, 10)
    tr = BeatTracker(RATE)
    beats = run(tr, x[: 4 * RATE])
    assert 115 <= tr.tempo_bpm <= 125, tr.tempo_bpm
    beats += run(tr, x[4 * RATE:], t0=1000.0 + 4)
    assert abs(len(beats) - len(clicks)) <= 0.05 * len(clicks), (len(beats), len(clicks))
    assert 115 <= beats[-1]["tempo_bpm"] <= 125


def test_beats_land_on_the_clicks():
    x, clicks = click_track(120, 10)
    beats = run(BeatTracker(RATE), x)
    clicks = np.asarray(clicks) + 1000.0
    errs = [np.min(np.abs(clicks - b["ts"])) for b in beats[8:]]
    assert np.median(errs) < 0.03


@pytest.mark.parametrize("bpm", [90, 140])
def test_other_tempos(bpm):
    x, _ = click_track(bpm, 10)
    tr = BeatTracker(RATE)
    run(tr, x)
    assert abs(tr.tempo_bpm - bpm) <= 0.05 * bpm, tr.tempo_bpm


def test_human_timing_jitter_still_tracks():
    x, clicks = click_track(120, 10, jitter_ms=15, seed=3)
    tr = BeatTracker(RATE)
    beats = run(tr, x)
    assert 115 <= tr.tempo_bpm <= 125
    assert abs(len(beats) - len(clicks)) <= 0.1 * len(clicks)


def test_silence_gives_no_beats():
    x = (0.0005 * np.random.default_rng(0).standard_normal(10 * RATE)).astype(np.float32)
    assert run(BeatTracker(RATE), x) == []
    assert run(BeatTracker(RATE), np.zeros(5 * RATE, np.float32)) == []


def test_beats_stop_when_music_stops():
    x, _ = click_track(120, 6)
    quiet = np.zeros(4 * RATE, np.float32)
    beats = run(BeatTracker(RATE), np.concatenate([x, quiet]))
    last = max(b["ts"] for b in beats) - 1000.0
    assert last < 6.0 + 0.6  # the grid stops once the last 0.5 s is quiet, not after the 1.5 s gate


def test_silent_flag_override_suppresses():
    x, _ = click_track(120, 5)
    assert run_with_flag(x) == []


def run_with_flag(x):
    tr = BeatTracker(RATE)
    beats = []
    for i in range(0, len(x), BLOCK):
        beats += tr.process(x[i:i + BLOCK], (i + BLOCK) / RATE, silent=True)
    return beats


def test_estimate_tempo_needs_history():
    assert estimate_tempo(np.zeros(10), 100.0) is None
    assert estimate_tempo(np.zeros(400), 100.0) is None


def test_processing_is_fast_enough_for_50ms_latency():
    x, _ = click_track(120, 5)
    tr = BeatTracker(RATE)
    run(tr, x[: 3 * RATE])
    t0 = time.perf_counter()
    n = 0
    for i in range(3 * RATE, 5 * RATE, BLOCK):
        tr.process(x[i:i + BLOCK], 2000 + i / RATE)
        n += 1
    per_block_ms = (time.perf_counter() - t0) * 1000 / n
    # The beat is published when its block is processed: block length (23 ms) + processing time.
    assert 23 + per_block_ms < 50, per_block_ms


def test_new_tempo_after_silence_is_picked_up_quickly():
    a, _ = click_track(120, 8)
    b, clicks_b = click_track(84, 10)
    tr = BeatTracker(RATE)
    beats = run(tr, np.concatenate([a, np.zeros(3 * RATE, np.float32), b]))
    after = [x for x in beats if x["ts"] - 1000.0 > 11.0]
    assert abs(len(after) - len(clicks_b)) <= 0.1 * len(clicks_b), (len(after), len(clicks_b))
    assert abs(tr.tempo_bpm - 84) < 4
