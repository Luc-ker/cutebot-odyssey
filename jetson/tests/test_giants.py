import cv2
import numpy as np

from jetson.calibration import Calibration
from jetson.giants import GiantDetector

W, H = 1280, 720
# Table occupies the middle of the frame, with floor visible around it.
CALIB = Calibration([[160, 90], [1120, 90], [1120, 630], [160, 630]], (W, H))


def empty_table():
    f = np.full((H, W, 3), 60, np.uint8)                                   # floor
    cv2.rectangle(f, (160, 90), (1120, 630), (150, 140, 130), -1)          # table top
    cv2.rectangle(f, (600, 300), (650, 360), (40, 90, 200), -1)            # a cup already there
    return f


def ready_detector(calib=CALIB):
    g = GiantDetector(calib)
    for _ in range(g.learn_frames):
        g.learn(empty_table())
    assert g.ready
    return g


def test_blob_growing_in_from_left_is_one_left_giant():
    g = ready_detector()
    results = []
    for reach in (40, 80, 140, 220):
        f = empty_table()
        # An arm from off-table (x < 160) reaching onto the table.
        cv2.rectangle(f, (100, 330), (160 + reach, 400), (190, 170, 210), -1)
        results.append(g.detect(f))
    for r in results:
        assert len(r) == 1
        assert r[0]["edge"] == "left"
    assert results[-1][0]["kind"] == "hand"  # mostly inside the table by then


def test_blob_in_middle_not_touching_edge_is_not_a_giant():
    g = ready_detector()
    f = empty_table()
    cv2.rectangle(f, (800, 300), (880, 380), (20, 200, 20), -1)  # an object dropped mid-table
    assert g.detect(f) == []


def test_mostly_outside_is_person():
    g = ready_detector()
    f = empty_table()
    cv2.rectangle(f, (300, 0), (600, 120), (200, 180, 160), -1)   # leaning in over the top edge
    r = g.detect(f)
    assert len(r) == 1 and r[0]["edge"] == "top" and r[0]["kind"] == "person"


def test_blob_off_table_is_ignored():
    g = ready_detector()
    f = empty_table()
    cv2.rectangle(f, (10, 10), (120, 80), (220, 220, 220), -1)  # someone walking past, off the table
    assert g.detect(f) == []


def test_empty_table_has_no_giants_and_learning_returns_empty():
    g = GiantDetector(CALIB)
    assert g.detect(empty_table()) == []  # still learning
    g = ready_detector()
    assert g.detect(empty_table()) == []


def test_person_detection_from_detector():
    g = ready_detector()
    r = g.detect(empty_table(), persons=[[1050, 200, 1250, 500]])
    assert len(r) == 1 and r[0]["kind"] == "person" and r[0]["edge"] == "right"


def test_without_calibration_uses_frame_edges():
    g = ready_detector(calib=None)
    f = empty_table()
    cv2.rectangle(f, (500, 600), (580, H - 1), (230, 230, 230), -1)  # enters from the bottom of the frame
    r = g.detect(f)
    assert len(r) == 1 and r[0]["edge"] == "bottom"


def test_reset_relearns():
    g = ready_detector()
    g.reset()
    assert not g.ready
