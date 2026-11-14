"""T110 — generic detector for objects the model has no name for."""
import cv2
import numpy as np

from jetson.calibration import Calibration
from jetson.detector import Detection
from jetson.generic_detector import GenericDetector

W, H = 1280, 720
TABLE = (160, 90, 1120, 630)  # x1, y1, x2, y2
CALIB = Calibration([[160, 90], [1120, 90], [1120, 630], [160, 630]], (W, H))
PACKET = (700, 380, 780, 440)  # a crisp packet, well inside the table


def table_frame(cup=True, brightness=0):
    f = np.full((H, W, 3), 60, np.uint8)                                           # floor
    cv2.rectangle(f, TABLE[:2], TABLE[2:], (150, 140, 130), -1)                    # table top
    if cup:
        cv2.rectangle(f, (400, 300), (450, 360), (40, 90, 200), -1)                # a cup, there all along
    noise = np.random.default_rng(len(str(brightness))).integers(-3, 4, f.shape)   # a little sensor noise
    return np.clip(f.astype(int) + noise + brightness, 0, 255).astype(np.uint8)


def with_box(frame, box, colour=(30, 30, 220)):
    f = frame.copy()
    cv2.rectangle(f, box[:2], box[2:], colour, -1)
    return f


def ready(calib=CALIB, **learn_from):
    g = GenericDetector(calib)
    for _ in range(g.learn_frames):
        assert g.detect(table_frame(**learn_from), []) == []   # learning: nothing reported yet
    assert g.ready
    return g


def close(bbox, box, tol=12):
    return all(abs(a - b) <= tol for a, b in zip(bbox, box))


# ---- acceptance ---------------------------------------------------------------------------------------------


def test_new_rectangle_on_empty_background_is_one_detection():
    g = ready()
    dets = g.detect(with_box(table_frame(), PACKET), [])
    assert len(dets) == 1
    d = dets[0]
    assert isinstance(d, Detection) and d.cls == "object"
    assert close(d.bbox, PACKET), d.bbox
    assert 0.3 <= d.conf <= 0.95


def test_same_rectangle_covered_by_a_known_detection_is_none():
    g = ready()
    known = [Detection(bbox=[695, 375, 785, 445], cls="cup", conf=0.8)]
    assert g.detect(with_box(table_frame(), PACKET), known) == []


# ---- what is not an object ------------------------------------------------------------------------------------


def test_blob_touching_the_table_edge_is_a_giant_not_an_object():
    g = ready()
    arm = (600, 0, 700, 300)  # from beyond the top edge onto the table
    assert g.detect(with_box(table_frame(), arm, (90, 120, 170)), []) == []


def test_specks_below_min_area_are_ignored():
    g = ready()
    assert g.detect(with_box(table_frame(), (800, 500, 806, 506)), []) == []


def test_robot_box_is_not_an_object():
    g = ready()
    assert g.detect(with_box(table_frame(), PACKET), [], robot_bbox=[690, 370, 790, 450]) == []


def test_partly_overlapping_known_box_still_lets_a_separate_object_through():
    g = ready()
    known = [Detection(bbox=[395, 295, 455, 365], cls="cup", conf=0.9)]  # the cup, elsewhere
    dets = g.detect(with_box(table_frame(), PACKET), known)
    assert len(dets) == 1 and close(dets[0].bbox, PACKET)


# ---- colour, lighting, ghosts, reset ----------------------------------------------------------------------------


def test_colour_change_with_the_same_brightness_is_found():
    g = ready()
    # same grey level as the table (~142) but clearly a different colour
    dets = g.detect(with_box(table_frame(), PACKET, (90, 150, 175)), [])
    assert len(dets) == 1


def test_lights_switched_relearns_instead_of_reporting_everything():
    g = ready()
    assert g.detect(table_frame(brightness=60), []) == []
    assert not g.ready  # learning again
    for _ in range(g.learn_frames):
        g.detect(table_frame(brightness=60), [])
    assert g.ready
    dets = g.detect(with_box(table_frame(brightness=60), PACKET), [])
    assert len(dets) == 1


def test_object_removed_after_learning_leaves_no_ghost():
    g = ready(cup=True)
    # the cup that was there while learning is taken away: its old spot now looks like the table
    assert g.detect(table_frame(cup=False), []) == []
    assert g.detect(table_frame(cup=False), []) == []  # absorbed, stays gone
    # and something new placed on that same spot is still found
    dets = g.detect(with_box(table_frame(cup=False), (400, 300, 460, 360)), [])
    assert len(dets) == 1


def test_slow_lighting_drift_is_followed():
    g = ready()
    for b in range(1, 30):  # +1 grey level per frame
        assert g.detect(table_frame(brightness=b), []) == []
    assert len(g.detect(with_box(table_frame(brightness=29), PACKET), [])) == 1


def test_reset_relearns():
    g = ready()
    g.reset()
    assert not g.ready
    assert g.detect(with_box(table_frame(), PACKET), []) == []  # learning again


def test_without_calibration_the_whole_frame_is_the_table():
    g = ready(calib=None)
    dets = g.detect(with_box(table_frame(), PACKET), [])
    assert len(dets) == 1


def test_pipeline_picks_it_up():
    from jetson.main import _generic_detector_class
    assert _generic_detector_class() is GenericDetector
