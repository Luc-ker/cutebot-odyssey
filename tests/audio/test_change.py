import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.audio.change import ChangeDetector, key_distance  # noqa: E402

RATE = 22050
NOTE = {n: i for i, n in enumerate("C C# D D# E F F# G G# A A# B".split())}


def make_song(name, secs, seed=0, offset=0.0):
    """Generated songs: A = bright C-major pop at 120 bpm, B = dark F#-minor ballad at 84 bpm."""
    bpm, chords, harmonics, amp = {
        "A": (120, [("C", 0), ("G", 0), ("A", 1), ("F", 0)], 8, 0.25),
        "B": (84, [("F#", 1), ("D", 0), ("A", 0), ("C#", 1)], 2, 0.18),
    }[name]
    rng = np.random.default_rng(seed)
    n = int(secs * RATE)
    t = np.arange(n) / RATE + offset
    beat = 60.0 / bpm
    x = np.zeros(n)
    idx = (t // (4 * beat)).astype(int) % 4
    for ci, (root, minor) in enumerate(chords):
        m = idx == ci
        for semis in (0, 3 if minor else 4, 7, 12):
            f = 130.81 * 2 ** ((NOTE[root] + semis) / 12)
            for h in range(1, harmonics + 1):
                x[m] += np.sin(2 * np.pi * f * h * t[m]) / h
    x *= amp / 4
    phase = (t % beat) / beat
    kick = np.ones(n, bool) if name == "A" else (t // beat).astype(int) % 2 == 0
    x += 0.5 * kick * np.exp(-phase * beat / 0.08) * np.sin(2 * np.pi * 55 * (t % beat))
    if name == "A":
        off = ((t + beat / 2) % beat) / beat
        x += 0.15 * np.exp(-off * beat / 0.02) * np.diff(rng.standard_normal(n + 1))
    else:
        x += 0.25 * ((t // beat).astype(int) % 2 == 1) * np.exp(-phase * beat / 0.05) * rng.standard_normal(n)
    return (x + 0.002 * rng.standard_normal(n)).astype(np.float32)


def silence(secs):
    return np.zeros(int(secs * RATE), np.float32)


def changes(x, block=512):
    d = ChangeDetector(RATE)
    out = []
    for i in range(0, len(x), block):
        chunk = x[i:i + block]
        t = (i + len(chunk)) / RATE
        if d.update(chunk, t):
            out.append(t)
    return out


@pytest.mark.parametrize("first,second", [("A", "B"), ("B", "A")])
def test_two_tracks_one_change_within_4s_of_switch(first, second):
    x = np.concatenate([make_song(first, 14, seed=1), make_song(second, 12, seed=2)])
    found = changes(x)
    assert len(found) == 1, found
    assert 14.0 <= found[0] <= 18.0, found


@pytest.mark.parametrize("name", ["A", "B"])
def test_single_steady_track_no_change(name):
    assert changes(make_song(name, 40)) == []


def test_steady_track_at_any_level_no_change():
    assert changes(0.25 * make_song("A", 30)) == []


def test_silence_to_music_is_a_change():
    found = changes(np.concatenate([silence(3), make_song("A", 10)]))
    assert len(found) == 1 and 3.0 <= found[0] <= 4.0, found


def test_music_pause_music_same_song():
    x = np.concatenate([make_song("A", 20), silence(3), make_song("A", 10, offset=20)])
    found = changes(x)
    assert len(found) == 1 and 23.0 <= found[0] <= 24.0, found  # fires on the return, not the stop


def test_short_gap_is_not_silence():
    x = np.concatenate([make_song("A", 20), silence(0.8), make_song("A", 10, offset=20)])
    assert changes(x) == []


def test_starting_mid_song_is_not_a_change():
    assert changes(make_song("B", 12, offset=5.0)) == []


def test_cooldown_6s():
    # three different sections 3 s apart: only the first counts inside the cooldown
    x = np.concatenate([make_song("A", 12), make_song("B", 3), make_song("A", 3), make_song("B", 6)])
    found = changes(x)
    assert all(b - a >= 6.0 for a, b in zip(found, found[1:])), found


def test_returns_true_once_per_change_not_per_frame():
    x = np.concatenate([make_song("A", 14), make_song("B", 12)])
    d = ChangeDetector(RATE)
    trues = sum(d.update(x[i:i + 512], (i + 512) / RATE) for i in range(0, len(x), 512))
    assert trues == 1


def test_key_distance_same_key_chords_close_other_key_far():
    def chroma(pcs):
        c = np.zeros(12)
        c[[NOTE[p] for p in pcs]] = 1
        return c
    c_major_i, c_major_v = chroma(["C", "E", "G"]), chroma(["G", "B", "D"])
    fs_minor = chroma(["F#", "A", "C#"])
    all_c = chroma(["C", "D", "E", "F", "G", "A", "B"])
    assert key_distance(c_major_i + c_major_v, all_c) < key_distance(fs_minor, all_c)
