import math

import pytest

from server.common.geometry import angle_diff, angle_to, cm_to_units, dist, in_cone, units_to_cm, wrap_angle

CFG = {"TABLE_W_CM": 120.0, "TABLE_H_CM": 80.0}


def test_dist():
    assert dist([0, 0], [0.3, 0.4]) == pytest.approx(0.5)


def test_angle_to_follows_c1():
    assert angle_to([0.5, 0.5], [0.6, 0.5]) == pytest.approx(0)
    assert angle_to([0.5, 0.5], [0.5, 0.6]) == pytest.approx(math.pi / 2)  # y down => clockwise positive
    assert angle_to([0.5, 0.5], [0.4, 0.5]) == pytest.approx(math.pi)


def test_angle_diff_wraps():
    assert angle_diff(math.pi - 0.1, -math.pi + 0.1) == pytest.approx(-0.2)
    assert angle_diff(-math.pi + 0.1, math.pi - 0.1) == pytest.approx(0.2)
    assert angle_diff(0.3, 0.1) == pytest.approx(0.2)


@pytest.mark.parametrize("a", [-10.0, -math.pi, 0.0, math.pi, 3 * math.pi, 7.5])
def test_wrap_range(a):
    w = wrap_angle(a)
    assert -math.pi < w <= math.pi
    assert math.isclose(math.cos(w), math.cos(a), abs_tol=1e-9)
    assert math.isclose(math.sin(w), math.sin(a), abs_tol=1e-9)


def test_wrap_minus_pi_maps_to_pi():
    assert wrap_angle(-math.pi) == pytest.approx(math.pi)


def test_in_cone():
    assert in_cone([0.5, 0.5], 0, [0.6, 0.5], 0.3, 0.2)
    assert not in_cone([0.5, 0.5], 0, [0.4, 0.5], 0.3, 0.2)  # behind
    assert not in_cone([0.5, 0.5], 0, [0.8, 0.5], 0.3, 0.2)  # too far
    assert not in_cone([0.5, 0.5], 0, [0.6, 0.6], 0.3, 0.2)  # 45 degrees off
    assert in_cone([0.5, 0.5], math.pi, [0.4, 0.5], 0.3, 0.2)  # facing the other way
    assert in_cone([0.5, 0.5], 1.0, [0.5, 0.5], 0.1, 0.2)  # same point


def test_cm_to_units():
    assert cm_to_units(12, "x", CFG) == pytest.approx(0.1)
    assert cm_to_units(8, "y", CFG) == pytest.approx(0.1)
    assert cm_to_units(8, 1, CFG) == pytest.approx(0.1)
    assert units_to_cm(0.1, "x", CFG) == pytest.approx(12)
    with pytest.raises(ValueError):
        cm_to_units(1, "z", CFG)


def test_cm_to_units_reads_shared_config():
    from server.common.config import load_config

    c = load_config()
    assert cm_to_units(c["TABLE_W_CM"], "x") == pytest.approx(1.0)
