import numpy as np
import pytest

from jetson.calibration import Calibration
from jetson.reid import ReId, compatible
from jetson.tracker import Track

# 1200x800 px table of 120x80 cm -> 10 px per cm.
CALIB = Calibration([[0, 0], [1200, 0], [1200, 800], [0, 800]], (1200, 800))
CFG = {"OBJECT_GRACE_S": 5.0, "TABLE_W_CM": 120.0, "TABLE_H_CM": 80.0}


def tr(tid, cx, cy, cls="cup", w=40):
    return Track(tid, cls, [cx - w / 2, cy - w / 2, cx + w / 2, cy + w / 2], 0.9)


def run(reid, frames):
    """frames: list of (ts, [tracks]); returns output ids per frame."""
    return [[t.id for t in reid.apply(tracks, ts)] for ts, tracks in frames]


def test_hidden_object_gets_old_id_back():
    reid = ReId(CFG, CALIB)
    out = run(reid, [
        (0.0, [tr(7, 500, 400)]),
        (0.5, [tr(7, 500, 400)]),
        (1.0, []),                       # hidden by a hand
        (2.5, []),
        (3.0, [tr(12, 530, 400)]),       # tracker gives a new id, 3 cm away
        (3.1, [tr(12, 531, 400)]),       # later frames keep the old id
    ])
    assert out == [[7], [7], [], [], [7], [7]]


def test_new_object_after_grace_gets_new_id():
    reid = ReId(CFG, CALIB)
    out = run(reid, [(0.0, [tr(7, 500, 400)]), (1.0, []), (7.0, [tr(12, 530, 400)])])
    assert out[-1] == [12]


def test_far_away_or_incompatible_class_is_new():
    reid = ReId(CFG, CALIB)
    out = run(reid, [
        (0.0, [tr(7, 500, 400)]),
        (1.0, []),
        (2.0, [tr(12, 800, 400)]),               # 30 cm away
        (2.1, [tr(12, 800, 400), tr(13, 505, 400, cls="scissors")]),
    ])
    assert out[2] == [12] and out[3] == [12, 13]


def test_compatible_classes():
    assert compatible("cup", "bowl")
    assert compatible("object", "bottle")
    assert not compatible("cup", "scissors")


def test_closest_candidate_wins_and_ids_stay_unique():
    reid = ReId(CFG, CALIB)
    run(reid, [(0.0, [tr(1, 500, 400), tr(2, 560, 400)]), (0.5, [])])
    out = reid.apply([tr(10, 555, 400), tr(11, 505, 400)], 1.0)
    assert {t.id: t.bbox[0] + 20 for t in out} == {2: 555, 1: 505}


def test_colour_histogram_blocks_a_different_looking_object():
    frame = np.zeros((800, 1200, 3), np.uint8)
    frame[380:420, 480:520] = (0, 0, 255)       # red cup
    reid = ReId(CFG, CALIB)
    reid.apply([tr(7, 500, 400)], 0.0, frame)
    reid.apply([], 1.0, frame)
    frame2 = np.zeros_like(frame)
    frame2[380:420, 500:540] = (255, 0, 0)      # a blue cup appears nearby
    out = reid.apply([tr(12, 520, 400)], 2.0, frame2)
    assert [t.id for t in out] == [12]


def test_without_calibration_uses_pixels():
    reid = ReId(CFG, None)
    out = run(reid, [(0.0, [tr(7, 500, 400)]), (1.0, []), (2.0, [tr(12, 530, 400)])])
    assert out[-1] == [7]


def test_reset_forgets():
    reid = ReId(CFG, CALIB)
    run(reid, [(0.0, [tr(7, 500, 400)]), (1.0, [])])
    reid.reset()
    assert [t.id for t in reid.apply([tr(12, 500, 400)], 2.0)] == [12]
