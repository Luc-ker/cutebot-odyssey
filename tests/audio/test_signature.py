import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.audio.signature import distance, signature, tempo_distance  # noqa: E402

RATE = 22050

# --- generated "songs" -----------------------------------------------------------------------
NOTE = {n: i for i, n in enumerate("C C# D D# E F F# G G# A A# B".split())}
SONGS = {
    # bright pop loop: C major, 120 bpm, buzzy chords, kick on beats and hi-hats on off-beats
    "A": dict(bpm=120, chords=[("C", 0), ("G", 0), ("A", 1), ("F", 0)], harmonics=8, hats=True, amp=0.25),
    # dark ballad: F# minor, 84 bpm, soft round chords, kick on 1 and 3, snare on 2 and 4, no hats
    "B": dict(bpm=84, chords=[("F#", 1), ("D", 0), ("A", 0), ("C#", 1)], harmonics=2, hats=False, amp=0.18),
}


def chord_freqs(root, minor):
    r = NOTE[root]
    return [130.81 * 2 ** ((r + s) / 12) for s in (0, 3 if minor else 4, 7, 12)]


def make_song(name, secs, rate=RATE, seed=0, offset=0.0):
    p = SONGS[name]
    rng = np.random.default_rng(seed)
    n = int(secs * rate)
    t = np.arange(n) / rate + offset
    beat = 60.0 / p["bpm"]
    bar = 4 * beat
    x = np.zeros(n)
    idx = (t // bar).astype(int) % len(p["chords"])
    for ci, (root, minor) in enumerate(p["chords"]):
        m = idx == ci
        for f in chord_freqs(root, minor):
            for h in range(1, p["harmonics"] + 1):
                x[m] += np.sin(2 * np.pi * f * h * t[m]) / h
    x *= p["amp"] / 4
    phase = (t % beat) / beat
    kick_beats = np.ones(n, bool) if name == "A" else ((t // beat).astype(int) % 2 == 0)
    env = np.exp(-phase * beat / 0.08)
    x += 0.5 * kick_beats * env * np.sin(2 * np.pi * 55 * (t % beat))
    if name == "B":  # snare on beats 2 and 4, so the pulse is really every beat
        snare_beats = (t // beat).astype(int) % 2 == 1
        x += 0.25 * snare_beats * np.exp(-phase * beat / 0.05) * rng.standard_normal(n)
    if p["hats"]:
        off = ((t + beat / 2) % beat) / beat
        x += 0.15 * np.exp(-off * beat / 0.02) * np.diff(rng.standard_normal(n + 1))
    return (x + 0.002 * rng.standard_normal(n)).astype(np.float32)


# --- tests -------------------------------------------------------------------------------------

def test_same_track_two_clips_close_different_tracks_far():
    a1 = signature(make_song("A", 8, seed=1), RATE)
    a2 = signature(make_song("A", 8, seed=2, offset=8.0), RATE)
    b1 = signature(make_song("B", 8, seed=3), RATE)
    b2 = signature(make_song("B", 8, seed=4, offset=11.4), RATE)
    assert distance(a1, a2) < 0.15, (a1, a2)
    assert distance(b1, b2) < 0.15, (b1, b2)
    assert distance(a1, b1) > 0.4, (a1, b1)
    assert distance(a2, b2) > 0.4


def test_same_song_quieter_and_shorter_still_matches():
    full = signature(make_song("A", 8, seed=1), RATE)
    quiet = signature(0.3 * make_song("A", 5, seed=9, offset=3), RATE)  # ~-10 dB, 5 s window
    assert distance(full, quiet) < 0.15


def test_fields_types_and_ranges():
    s = signature(make_song("A", 6), RATE)
    assert set(s) == {"tempo_bpm", "energy", "brightness", "chroma"}
    assert len(s["chroma"]) == 12 and abs(np.linalg.norm(s["chroma"]) - 1) < 1e-3
    assert 0 <= s["energy"] <= 1 and 0 <= s["brightness"] <= 1
    json.dumps(s)  # stored in the world JSON (C4)


def test_tempo_found():
    assert abs(signature(make_song("A", 8), RATE)["tempo_bpm"] - 120) < 6
    b = signature(make_song("B", 8), RATE)["tempo_bpm"]
    assert tempo_distance(b, 84) < 0.25, b


def test_chroma_peaks_on_the_key():
    a = signature(make_song("A", 8), RATE)["chroma"]
    top = {int(i) for i in np.argsort(a)[-3:]}
    assert top <= {NOTE[n] for n in ("C", "D", "E", "F", "G", "A", "B")}  # C major scale


def test_tempo_distance_is_octave_aware():
    assert tempo_distance(60, 120) == 0
    assert tempo_distance(120, 120) == 0
    assert tempo_distance(120, 90) == 1
    assert tempo_distance(0, 120) is None


def test_distance_bounds_and_symmetry():
    a = signature(make_song("A", 5), RATE)
    b = signature(make_song("B", 5), RATE)
    assert distance(a, a) == 0
    assert distance(a, b) == distance(b, a)
    assert 0 <= distance(a, b) <= 1


def test_unknown_tempo_is_ignored_not_penalised():
    a = signature(make_song("A", 6), RATE)
    assert distance(a, {**a, "tempo_bpm": 0.0}) == 0


def test_silence_signature_is_safe():
    s = signature(np.zeros(RATE * 3, np.float32), RATE)
    assert s["tempo_bpm"] == 0 and s["energy"] == 0 and s["chroma"] == [0.0] * 12
    assert 0 <= distance(s, signature(make_song("A", 3), RATE)) <= 1
