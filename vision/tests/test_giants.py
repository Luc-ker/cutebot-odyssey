import cv2
import numpy as np

from vision.detector import Detection
from vision.giants import GiantDetector

W, H = 1280, 720
SKIN = (120, 150, 210)        # BGR, a typical skin tone (YCrCb Cr≈155, Cb≈105)
WOOD = (40, 90, 140)          # BGR, a brown wooden table
BLUE_CUP = (200, 90, 40)


def robot_view():
    """Low view of a table: wall at the top, table surface filling the bottom half, a cup on it."""
    f = np.full((H, W, 3), (190, 190, 185), np.uint8)               # pale wall
    cv2.rectangle(f, (0, 420), (W, H), (90, 90, 95), -1)             # grey table top
    cv2.rectangle(f, (600, 330), (680, 440), BLUE_CUP, -1)           # a cup
    return f


def test_plain_view_has_no_giants():
    assert GiantDetector().detect(robot_view()) == []


def test_hand_reaching_down_from_the_top_is_a_hand_giant():
    f = robot_view()
    cv2.rectangle(f, (500, 0), (700, 380), SKIN, -1)                 # forearm and hand coming down
    giants = GiantDetector().detect(f)
    assert len(giants) == 1
    g = giants[0]
    assert g["kind"] == "hand" and g["edge"] == "top"
    x1, y1, x2, y2 = g["bbox"]
    assert x1 < 520 and x2 > 680 and y1 < 10 and y2 > 360


def test_hand_from_the_side_is_a_giant():
    f = robot_view()
    cv2.rectangle(f, (W - 300, 250), (W, 400), SKIN, -1)
    giants = GiantDetector().detect(f)
    assert [(g["kind"], g["edge"]) for g in giants] == [("hand", "right")]


def test_wooden_table_along_the_bottom_is_not_a_giant():
    f = robot_view()
    cv2.rectangle(f, (0, 420), (W, H), WOOD, -1)                     # skin-ish wood touching bottom and sides
    cv2.rectangle(f, (0, 430), (W, H), SKIN, -1)                     # even if it really matches skin
    assert GiantDetector().detect(f) == []


def test_small_skin_coloured_object_is_not_a_giant():
    f = robot_view()
    cv2.rectangle(f, (300, 0), (330, 30), SKIN, -1)                  # tiny, touching the top
    assert GiantDetector().detect(f) == []


def test_person_detection_is_a_person_giant_and_wins_over_a_hand():
    f = robot_view()
    cv2.rectangle(f, (500, 0), (700, 380), SKIN, -1)
    person = Detection([480, 0, 720, 400], "person", 0.8)
    giants = GiantDetector().detect(f, [person])
    assert [(g["kind"], g["edge"]) for g in giants] == [("person", "top")]
    far = Detection([1000, 100, 1200, 300], "person", 0.9)
    giants = GiantDetector().detect(robot_view(), [far])
    assert [(g["kind"], g["edge"]) for g in giants] == [("person", "right")]
    assert GiantDetector().detect(robot_view(), [Detection([0, 0, 50, 50], "person", 0.2)]) == []
