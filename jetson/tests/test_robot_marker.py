import math

import cv2
import numpy as np
import pytest

from jetson.robot_marker import find_robot, render_marker


def scene_with_marker(angle_deg: float, centre=(640, 360), size=120, marker_id=7):
    """A grey table with the marker pasted at `centre`, rotated counter-clockwise by `angle_deg` on screen."""
    frame = np.full((720, 1280, 3), 170, np.uint8)
    m = cv2.cvtColor(render_marker(size, marker_id), cv2.COLOR_GRAY2BGR)
    h, w = m.shape[:2]
    x, y = centre[0] - w // 2, centre[1] - h // 2
    frame[y:y + h, x:x + w] = m
    rot = cv2.getRotationMatrix2D(centre, angle_deg, 1.0)
    return cv2.warpAffine(frame, rot, (1280, 720), borderValue=(170, 170, 170))


def ang_err(a, b):
    return abs(math.atan2(math.sin(a - b), math.cos(a - b)))


def test_unrotated_marker_points_up():
    r = find_robot(scene_with_marker(0))
    assert r is not None and r["method"] == "aruco"
    assert ang_err(r["heading"], -math.pi / 2) < math.radians(2)
    assert r["px"] == pytest.approx([640, 360], abs=2)


def test_rotated_30_degrees_heading_within_5():
    # warpAffine with +30 turns the image counter-clockwise on screen; with y down, the marker's
    # "up" (-90°) becomes -120°.
    r = find_robot(scene_with_marker(30))
    assert r is not None
    assert ang_err(r["heading"], math.radians(-120)) < math.radians(5)
    x1, y1, x2, y2 = r["bbox"]
    assert x1 < 640 < x2 and y1 < 360 < y2


@pytest.mark.parametrize("angle", [-150, -45, 90, 179])
def test_other_angles(angle):
    r = find_robot(scene_with_marker(angle))
    assert ang_err(r["heading"], math.radians(-90 - angle)) < math.radians(5)


def test_absent_returns_none():
    assert find_robot(np.full((720, 1280, 3), 170, np.uint8)) is None
    assert find_robot(scene_with_marker(0, marker_id=3)) is None  # wrong id
    assert find_robot(None) is None
    assert find_robot(np.zeros((0, 0, 3), np.uint8)) is None


def test_coloured_dots_fallback():
    frame = np.full((720, 1280, 3), 170, np.uint8)
    cv2.circle(frame, (700, 400), 10, (0, 200, 0), -1)      # green front
    cv2.circle(frame, (640, 400), 10, (200, 0, 200), -1)    # magenta back
    r = find_robot(frame)
    assert r is not None and r["method"] == "dots"
    assert ang_err(r["heading"], 0.0) < math.radians(3)
    assert r["px"] == pytest.approx([670, 400], abs=2)
