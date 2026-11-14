import importlib.util
from pathlib import Path

import numpy as np
import pytest

from jetson.calibration import Calibration
from jetson.detector import Detection, Detector, filter_detections

CALIB = Calibration([[200, 100], [1080, 100], [1080, 620], [200, 620]], (1280, 720))
SHAPE = (720, 1280, 3)
SAMPLE = Path(__file__).resolve().parent / "data" / "table.jpg"


def d(bbox, cls="cup", conf=0.9):
    return Detection(list(map(float, bbox)), cls, conf)


def test_keeps_good_detection():
    keep = d([500, 300, 560, 360])
    assert filter_detections([keep], CALIB, SHAPE) == [keep]


def test_drops_detection_fully_outside_table():
    outside = d([20, 20, 120, 90], "bottle")
    assert filter_detections([outside], CALIB, SHAPE) == []


def test_keeps_detection_straddling_table_edge():
    straddle = d([150, 300, 260, 380], "book")
    assert filter_detections([straddle], CALIB, SHAPE) == [straddle]


@pytest.mark.parametrize("bad", [
    d([500, 300, 560, 360], "person"),        # not a table object (giants handle people)
    d([500, 300, 560, 360], "cup", 0.1),      # low confidence
    d([500, 300, 505, 360], "cup"),           # too thin
    d([210, 110, 1070, 610], "dining table"), # the table itself
    d([0, 0, 1280, 720], "laptop"),           # covers most of the frame
])
def test_drops_bad_detections(bad):
    assert filter_detections([bad], CALIB, SHAPE) == []


def test_without_calibration_keeps_everything_useful():
    assert len(filter_detections([d([20, 20, 120, 90])], None, SHAPE)) == 1


def test_detect_uses_raw_when_given():
    det = Detector(calib=CALIB)
    raw = [d([500, 300, 560, 360]), d([20, 20, 120, 90]), d([600, 300, 700, 500], "person")]
    out = det.detect(np.zeros(SHAPE, np.uint8), raw=raw)
    assert [x.cls for x in out] == ["cup"]


@pytest.mark.slow
@pytest.mark.skipif(importlib.util.find_spec("ultralytics") is None or not SAMPLE.exists(),
                    reason="needs ultralytics and jetson/tests/data/table.jpg (photo of the demo table)")
def test_finds_known_items_in_sample_image():
    import cv2

    frame = cv2.imread(str(SAMPLE))
    found = {x.cls for x in Detector().detect(frame)}
    assert {"cup", "bottle"} <= found, found
