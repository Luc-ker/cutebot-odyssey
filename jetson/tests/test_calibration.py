import cv2
import numpy as np
import pytest

from jetson.calibrate_tool import find_aruco_corners
from jetson.calibration import Calibration

# A skewed quadrilateral, as a tilted camera would see the table.
CORNERS = [[200, 120], [1100, 150], [1180, 650], [120, 620]]


@pytest.fixture
def calib():
    return Calibration(CORNERS, (1280, 720))


def test_corners_map_to_unit_square(calib):
    expected = [[0, 0], [1, 0], [1, 1], [0, 1]]
    for px, xy in zip(CORNERS, expected):
        assert calib.to_table(px) == pytest.approx(xy, abs=1e-6)


@pytest.mark.parametrize("p", [[640, 380], [300, 200], [1000, 600], [500, 140]])
def test_round_trip(calib, p):
    assert calib.to_pixel(calib.to_table(p)) == pytest.approx(p, abs=1e-6)


def test_clamped_to_unit_square(calib):
    x, y = calib.to_table([10, 10])
    assert 0 <= x <= 1 and 0 <= y <= 1
    raw = calib.to_table_raw([10, 10])
    assert raw[0] < 0 and raw[1] < 0


def test_contains(calib):
    assert calib.contains([640, 380])
    assert not calib.contains([10, 10])
    assert not calib.contains([640, 700])


def test_edge_of(calib):
    top_mid = calib.to_pixel([0.5, 0.0])
    assert calib.edge_of([top_mid[0], top_mid[1] - 5]) == "top"  # just above the top edge
    assert calib.edge_of(calib.to_pixel([0.02, 0.5])) == "left"
    assert calib.edge_of(calib.to_pixel([0.5, 1.1])) == "bottom"
    assert calib.edge_of(calib.to_pixel([1.3, 0.4])) == "right"
    assert calib.edge_of(calib.to_pixel([0.5, 0.5]), margin=0.1) is None
    assert calib.edge_of(calib.to_pixel([0.95, 0.5]), margin=0.1) == "right"


def test_save_load(calib, tmp_path):
    path = tmp_path / "calibration.json"
    calib.save(path)
    again = Calibration.load(path)
    assert again.to_table([640, 380]) == pytest.approx(calib.to_table([640, 380]))
    assert again.image_size == (1280, 720)


def test_identity_and_mask():
    c = Calibration.identity(640, 480)
    assert c.to_table([320, 240]) == pytest.approx([0.5, 0.5])
    m = Calibration(CORNERS).mask((720, 1280, 3))
    assert m[380, 640] == 255 and m[10, 10] == 0


def test_box_overlaps_table(calib):
    assert calib.box_overlaps_table([600, 300, 700, 400])
    assert calib.box_overlaps_table([150, 100, 260, 160])  # straddles a corner
    assert not calib.box_overlaps_table([0, 0, 50, 50])


def test_aruco_auto_corners():
    frame = np.full((720, 1280, 3), 255, np.uint8)
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    size = 80
    spots = {0: (100, 100), 1: (1100, 100), 2: (1100, 540), 3: (100, 540)}
    for mid, (x, y) in spots.items():
        img = cv2.aruco.generateImageMarker(d, mid, size)
        frame[y:y + size, x:x + size] = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    corners = find_aruco_corners(frame)
    assert corners is not None
    expected = [[100, 100], [1179, 100], [1179, 619], [100, 619]]
    for got, exp in zip(corners, expected):
        assert got == pytest.approx(exp, abs=3)
