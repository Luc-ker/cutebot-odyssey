import importlib.util
from pathlib import Path

import numpy as np
import pytest

from vision.detector import Detection, Detector, filter_detections

SHAPE = (720, 1280, 3)
SAMPLE = Path(__file__).resolve().parent / "data" / "table.jpg"


def d(bbox, cls="cup", conf=0.9):
    return Detection(list(map(float, bbox)), cls, conf)


def test_keeps_good_detection():
    keep = d([500, 300, 560, 360])
    assert filter_detections([keep], SHAPE) == [keep]


def test_keeps_close_object_filling_much_of_the_view():
    close = d([200, 50, 1100, 700], "bottle")  # right in front of the robot
    assert filter_detections([close], SHAPE) == [close]


@pytest.mark.parametrize("bad", [
    d([500, 300, 560, 360], "person"),        # not an object (giants handle people)
    d([500, 300, 560, 360], "cup", 0.1),      # low confidence
    d([500, 300, 505, 360], "cup"),           # too thin
    d([210, 110, 1070, 610], "dining table"), # the table itself
    d([0, 0, 1280, 720], "laptop"),           # covers the whole frame
])
def test_drops_bad_detections(bad):
    assert filter_detections([bad], SHAPE) == []


def test_detect_uses_raw_when_given():
    det = Detector()
    raw = [d([500, 300, 560, 360]), d([20, 20, 120, 90], "bottle"), d([600, 300, 700, 500], "person")]
    out = det.detect(np.zeros(SHAPE, np.uint8), raw=raw)
    assert [x.cls for x in out] == ["cup", "bottle"]


@pytest.mark.slow
@pytest.mark.skipif(importlib.util.find_spec("ultralytics") is None or not SAMPLE.exists(),
                    reason="needs ultralytics and vision/tests/data/table.jpg (a robot's-eye photo of the demo table)")
def test_finds_known_items_in_sample_image():
    import cv2

    frame = cv2.imread(str(SAMPLE))
    found = {x.cls for x in Detector().detect(frame)}
    assert {"cup", "bottle"} <= found, found


# ---------------------------------------------------------------- outlines for the local renderer

from vision.detector import OUTLINE_POINTS, default_model_path, model_task, resample_outline  # noqa: E402


def test_resample_outline_keeps_short_contours_and_thins_long_ones():
    square = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert resample_outline(square) == [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    circle = [[100 + 50 * np.cos(a), 100 + 50 * np.sin(a)] for a in np.linspace(0, 2 * np.pi, 400, endpoint=False)]
    out = resample_outline(circle)
    assert len(out) == OUTLINE_POINTS
    assert all(abs(np.hypot(x - 100, y - 100) - 50) < 1 for x, y in out)  # still on the circle
    assert resample_outline([[0, 0], [1, 1]]) == [] and resample_outline(None) == []


def test_model_task_and_openvino_export_preferred(tmp_path):
    assert model_task("vision/models/yolo11n-seg.pt") == "segment"
    assert model_task("vision/models/yolo11n-seg_openvino_model") == "segment"
    assert model_task("vision/models/yolo11n.pt") == "detect"
    assert default_model_path("yolo11n-seg", tmp_path).endswith("yolo11n-seg.pt")
    (tmp_path / "yolo11n-seg_openvino_model").mkdir()
    assert default_model_path("yolo11n-seg", tmp_path).endswith("yolo11n-seg_openvino_model")
