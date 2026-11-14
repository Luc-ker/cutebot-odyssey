import math

import pytest

from jetson.calibration import Calibration
from jetson.robot_pose import RobotPose

CALIB = Calibration([[0, 0], [1000, 0], [1000, 1000], [0, 1000]], (1000, 1000))  # 1 px = 0.001 units
DT = 0.1


def m(u, v, heading=0.0):
    return {"px": [u, v], "heading": heading, "bbox": [u - 10, v - 10, u + 10, v + 10]}


def test_first_measurement_sets_pose():
    p = RobotPose(CALIB)
    s = p.update(m(500, 500, 0.3), 0.0)
    assert s["pos"] == pytest.approx([0.5, 0.5]) and s["heading"] == pytest.approx(0.3) and s["seen"]


def test_unseen_before_any_measurement():
    assert RobotPose(CALIB).update(None, 0.0) == {"pos": None, "heading": None, "seen": False}


def test_single_outlier_is_ignored():
    p = RobotPose(CALIB)
    for i in range(5):
        p.update(m(500 + 5 * i, 500), i * DT)
    before = p.update(m(525, 500), 5 * DT)["pos"]
    after = p.update(m(950, 100), 6 * DT)  # 0.6 units in 0.1 s: impossible
    assert after["pos"] == pytest.approx(before)
    nxt = p.update(m(530, 500), 7 * DT)
    assert nxt["pos"][0] == pytest.approx(0.5275, abs=0.01) and nxt["seen"]


def test_none_keeps_last_pose_unseen_and_stays_frozen():
    p = RobotPose(CALIB)
    last = p.update(m(400, 300, 1.0), 0.0)
    for i in range(1, 60):  # 6 s of nothing
        s = p.update(None, i * DT)
        assert s["pos"] == last["pos"] and s["heading"] == last["heading"] and s["seen"] is False


def test_reacquire_after_loss_allows_proportional_move():
    p = RobotPose(CALIB)
    p.update(m(400, 300), 0.0)
    for i in range(1, 20):
        p.update(None, i * DT)
    s = p.update(m(700, 300), 2.0)  # 0.3 units in 2 s is plausible
    assert s["seen"] and s["pos"][0] > 0.5


def test_relocks_after_consistent_jumps():
    p = RobotPose(CALIB)
    p.update(m(100, 100), 0.0)
    for i in range(1, 6):
        s = p.update(m(900, 900), i * 0.02)  # robot picked up and put down elsewhere
    assert s["pos"] == pytest.approx([0.9, 0.9], abs=1e-6)


def test_position_is_smoothed():
    p = RobotPose(CALIB)
    p.update(m(500, 500), 0.0)
    s = p.update(m(520, 500), DT)
    assert 0.5 < s["pos"][0] < 0.52


def test_heading_smoothing_across_wrap():
    p = RobotPose(CALIB)
    p.update(m(500, 500, math.pi - 0.1), 0.0)
    s = p.update(m(500, 500, -math.pi + 0.1), DT)
    # Halfway along the short arc is ±π, not 0.
    assert abs(abs(s["heading"]) - math.pi) < 1e-6
    for i in range(2, 20):
        s = p.update(m(500, 500, -math.pi + 0.1), i * DT)
    assert s["heading"] == pytest.approx(-math.pi + 0.1, abs=1e-3)


def test_heading_accounts_for_perspective():
    # Table is squashed vertically in the image (2:1 px aspect): 45° in pixels is steeper in table units.
    c = Calibration([[0, 0], [1000, 0], [1000, 500], [0, 500]])
    s = RobotPose(c).update(m(500, 250, math.pi / 4), 0.0)
    assert s["heading"] == pytest.approx(math.atan2(2, 1), abs=1e-3)
