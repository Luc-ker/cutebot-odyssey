import math

import pytest

from server.common.geometry import angle_diff, angle_to, bearing, dist, view_size, wrap_angle


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


def test_bearing_from_view_x():
    assert bearing(0.5, 60) == pytest.approx(0)
    assert bearing(1.0, 60) == pytest.approx(math.radians(30))
    assert bearing(0.0, 60) == pytest.approx(-math.radians(30))
    assert bearing(0.75, 60) == pytest.approx(math.atan(0.5 * math.tan(math.radians(30))))  # pinhole, not linear


def test_view_size():
    assert view_size([0.2, 0.5]) == 0.5
    assert view_size(None) == 0.0
    assert view_size([]) == 0.0
