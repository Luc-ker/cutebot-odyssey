import math

import numpy as np
import pytest

from jetson.calibration import Calibration
from jetson.detector import Detection
from jetson.main import Pipeline
from jetson.state import GiantIds, build_state, overlaps_robot
from jetson.tracker import Track

CALIB = Calibration([[100, 50], [1100, 50], [1100, 550], [100, 550]], (1280, 720))  # 1000x500 px table

try:
    from server.common.schemas import validate_envelope
except ImportError:  # T04 not merged
    validate_envelope = None


def envelope(data):
    return {"topic": "vision.state", "ts": 1.0, "src": "jetson", "data": data}


def test_build_state_basic_and_schema():
    tracks = [Track(3, "cup", [580, 280, 620, 320], 0.91), Track(4, "book", [90, 40, 160, 100], 0.8)]
    pose = {"pos": [0.2, 0.7], "heading": 1.2, "seen": True}
    giants = [{"id": "g1", "bbox": [0, 200, 300, 300], "kind": "hand", "edge": "left"}]
    s = build_state(tracks, pose, giants, CALIB, 12.5)
    assert s["frame_ts"] == 12.5
    assert s["objects"][0] == {"id": 3, "cls": "cup", "pos": pytest.approx([0.5, 0.5]),
                               "size": pytest.approx([0.04, 0.08]), "conf": 0.91}
    assert s["robot"] == {"pos": [0.2, 0.7], "heading": 1.2, "seen": True}
    assert s["giants"][0]["id"] == "g1" and s["giants"][0]["edge"] == "left"
    for o in s["objects"] + s["giants"]:
        assert all(0 <= v <= 1 for v in o["pos"] + o["size"])  # the straddling book is clamped
    if validate_envelope:
        assert validate_envelope(envelope(s)) == []


def test_track_overlapping_robot_is_excluded():
    robot_bbox = [500, 250, 600, 350]
    phone = Track(9, "cell phone", [530, 260, 570, 300], 0.95)   # standing on the robot
    cup = Track(3, "cup", [800, 300, 840, 340], 0.9)
    s = build_state([phone, cup], {"pos": [0.5, 0.5], "heading": 0.0, "seen": True}, [], CALIB, 1.0, robot_bbox)
    assert [o["id"] for o in s["objects"]] == [3]


def test_overlaps_robot():
    rb = [100, 100, 200, 200]
    assert overlaps_robot([150, 150, 170, 170], rb)
    assert not overlaps_robot([180, 100, 260, 200], rb)    # 25 % covered, centre outside
    assert overlaps_robot([160, 100, 240, 200], rb)        # 50 % covered
    assert not overlaps_robot([190, 100, 290, 200], rb)
    assert not overlaps_robot([150, 150, 170, 170], None)


def test_no_robot_and_wrap():
    assert build_state([], None, [], CALIB, 1.0)["robot"] is None
    assert build_state([], {"pos": None, "heading": None, "seen": False}, [], CALIB, 1.0)["robot"] is None
    s = build_state([], {"pos": [0.5, 0.5], "heading": -math.pi, "seen": False}, [], CALIB, 1.0)
    assert s["robot"]["heading"] == pytest.approx(math.pi)
    if validate_envelope:
        assert validate_envelope(envelope(s)) == []


def test_giant_ids_are_stable():
    ids = GiantIds()
    a = ids.assign([{"bbox": [0, 200, 100, 300], "kind": "hand", "edge": "left"}], 0.0)
    b = ids.assign([{"bbox": [0, 210, 140, 310], "kind": "hand", "edge": "left"},
                    {"bbox": [500, 0, 600, 80], "kind": "hand", "edge": "top"}], 0.1)
    assert a[0]["id"] == b[0]["id"] == "g1" and b[1]["id"] == "g2"
    c = ids.assign([{"bbox": [0, 200, 100, 300], "kind": "hand", "edge": "left"}], 5.0)  # came back later
    assert c[0]["id"] == "g3"


class FakeDetector:
    calib = None

    def __init__(self, raw):
        self.raw = raw

    def detect_all(self, frame):
        return self.raw

    def detect(self, frame, raw=None):
        return [d for d in (raw or self.raw) if d.cls != "person"]


def test_pipeline_end_to_end_with_fakes():
    frame = np.full((720, 1280, 3), 150, np.uint8)
    det = FakeDetector([Detection([580, 280, 620, 320], "cup", 0.9)])
    p = Pipeline({"OBJECT_GRACE_S": 5}, CALIB, det, giants=False, generic=False)
    s1 = p.process(frame, 0.0)
    s2 = p.process(frame, 0.1)
    assert [o["id"] for o in s1["objects"]] == [o["id"] for o in s2["objects"]] == [1]
    assert s2["robot"] is None
    p.request_reset()
    s3 = p.process(frame, 0.2)
    assert s3["objects"][0]["id"] != 1  # reset forgets tracks; ids never repeat
