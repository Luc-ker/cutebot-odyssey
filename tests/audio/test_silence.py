import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.audio.silence import LOUD_AFTER_S, SILENT_AFTER_S, SilenceGate  # noqa: E402

DT = 0.05  # 20 Hz frames
rng = np.random.default_rng(1)


def music(n):  # fluctuating loud level
    return 0.08 + 0.05 * np.abs(rng.standard_normal(n))


def room(n):  # quiet room noise
    return 0.0008 + 0.0003 * np.abs(rng.standard_normal(n))


def run(gate, levels, t0):
    states = []
    for i, r in enumerate(levels):
        states.append((t0 + i * DT, gate.update(r, t0 + i * DT)))
    return states, t0 + len(levels) * DT


def flips(states):
    return [(t, s) for (t, s), (_, p) in zip(states[1:], states) if s != p]


def test_music_silence_music_flips_twice_with_stated_delays():
    gate = SilenceGate()
    # warm up on room noise so the floor is learned, then: music 5 s, silence 4 s, music 3 s
    _, t = run(gate, room(40), 0.0)
    assert gate.silent
    seq = np.concatenate([music(100), room(80), music(60)])
    states, _ = run(gate, seq, t)
    f = flips(states)
    # the initial loud flip, then silent, then loud again
    assert [s for _, s in f] == [False, True, False]
    music_start, silence_start, music2_start = t, t + 100 * DT, t + 180 * DT
    assert abs((f[0][0] - music_start) - LOUD_AFTER_S) <= DT + 1e-9
    assert abs((f[1][0] - silence_start) - SILENT_AFTER_S) <= DT + 1e-9
    assert abs((f[2][0] - music2_start) - LOUD_AFTER_S) <= DT + 1e-9


def test_short_gaps_do_not_flip():
    gate = SilenceGate(start_silent=False)
    seq = np.concatenate([music(40), room(20), music(40)])  # 1 s gap < 1.5 s
    states, _ = run(gate, seq, 0.0)
    assert not any(s for _, s in states)


def test_brief_click_in_silence_does_not_flip():
    gate = SilenceGate()
    seq = np.concatenate([room(40), music(4), room(40)])  # 0.2 s blip < 0.3 s
    states, _ = run(gate, seq, 0.0)
    assert all(s for _, s in states)


def test_floor_adapts_to_noisier_room_while_silent():
    gate = SilenceGate()
    noisy = 0.003 + 0.0005 * np.abs(rng.standard_normal(200))  # louder room, still not music
    states, _ = run(gate, noisy, 0.0)
    assert states[-1][1] is True
    assert gate.threshold > 0.003


def test_long_music_never_becomes_silence():
    gate = SilenceGate()
    states, _ = run(gate, music(20 * 60), 0.0)  # one minute
    assert states[-1][1] is False
    assert not any(s for _, s in states[20:])


def test_gate_started_over_music_still_works():
    gate = SilenceGate(start_silent=True)
    _, t = run(gate, music(60), 0.0)
    assert gate.silent is False
    states, _ = run(gate, room(60), t)
    assert states[-1][1] is True


def test_digital_zero_is_silent():
    gate = SilenceGate(start_silent=False)
    states, _ = run(gate, np.zeros(40), 0.0)
    assert states[-1][1] is True
