import asyncio
import base64

import cv2
import numpy as np
import pytest

from vision.detector import Detection
from vision.frames import HubFrames, decode_frame
from vision.main import NullDetector, Pipeline
from vision.state import GiantIds, box_to_view, build_state
from vision.tracker import Track

SHAPE = (720, 1280, 3)

try:
    from server.common.schemas import validate_envelope
except ImportError:  # T04 not merged
    validate_envelope = None


def envelope(data):
    return {"topic": "vision.state", "ts": 1.0, "src": "vision", "data": data}


def test_build_state_in_view_units_and_schema():
    tracks = [Track(3, "cup", [608, 324, 672, 396], 0.91), Track(4, "book", [-20, 600, 128, 760], 0.8)]
    giants = [{"id": "g1", "bbox": [0, 0, 320, 360], "kind": "hand", "edge": "top"}]
    s = build_state(tracks, giants, SHAPE, 12.5)
    assert s["frame_ts"] == 12.5
    assert s["objects"][0] == {"id": 3, "cls": "cup", "pos": pytest.approx([0.5, 0.5]),
                               "size": pytest.approx([0.05, 0.1]), "conf": 0.91}
    assert "robot" not in s  # the camera is the robot
    assert s["giants"][0]["id"] == "g1" and s["giants"][0]["edge"] == "top"
    assert s["giants"][0]["pos"] == pytest.approx([0.125, 0.25])
    for o in s["objects"] + s["giants"]:
        assert all(0 <= v <= 1 for v in o["pos"] + o["size"])  # the book hanging off the frame is clamped
    if validate_envelope:
        assert validate_envelope(envelope(s)) == []


def test_box_to_view_clamps():
    pos, size = box_to_view([-100, -100, 640, 360], SHAPE)
    assert pos == pytest.approx([0.25, 0.25]) and size == pytest.approx([0.5, 0.5])


def test_giant_ids_are_stable():
    ids = GiantIds()
    a = ids.assign([{"bbox": [0, 200, 100, 300], "kind": "hand", "edge": "left"}], 0.0)
    b = ids.assign([{"bbox": [0, 210, 140, 310], "kind": "hand", "edge": "left"},
                    {"bbox": [500, 0, 600, 80], "kind": "hand", "edge": "top"}], 0.1)
    assert a[0]["id"] == b[0]["id"] == "g1" and b[1]["id"] == "g2"
    c = ids.assign([{"bbox": [0, 200, 100, 300], "kind": "hand", "edge": "left"}], 5.0)  # came back later
    assert c[0]["id"] == "g3"


class FakeDetector:
    def __init__(self, raw):
        self.raw = raw

    def detect_all(self, frame):
        return self.raw

    def detect(self, frame, raw=None):
        return [d for d in (raw or self.raw) if d.cls != "person"]


def test_pipeline_end_to_end_with_fakes():
    frame = np.full((720, 1280, 3), 150, np.uint8)
    det = FakeDetector([Detection([580, 280, 620, 320], "cup", 0.9)])
    p = Pipeline({"OBJECT_FORGET_S": 600}, det, giants=False)
    states = [p.process(frame, i * 0.1) for i in range(4)]
    assert states[0]["objects"] == []  # a box must be seen in a few frames before it counts
    ids = [o["id"] for o in states[-1]["objects"]]
    assert len(ids) == 1
    p.request_reset()
    later = [p.process(frame, 1 + i * 0.1) for i in range(4)][-1]
    assert later["objects"][0]["id"] != ids[0]  # reset forgets tracks; ids never repeat
    if validate_envelope:
        assert validate_envelope(envelope(later)) == []


def test_pipeline_without_a_model_still_runs():
    p = Pipeline({}, NullDetector("no model"), giants=True)
    s = p.process(np.full((360, 640, 3), 90, np.uint8), 0.0)
    assert s["objects"] == [] and s["giants"] == []


# ---------------------------------------------------------------- frames from the hub

def _jpeg_b64(img) -> str:
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return base64.b64encode(buf.tobytes()).decode()


def test_decode_frame_round_trip_and_rejects_rubbish():
    img = np.zeros((90, 160, 3), np.uint8)
    img[:, :80] = (0, 0, 255)
    out = decode_frame({"jpeg": _jpeg_b64(img)})
    assert out.shape == (90, 160, 3) and out[45, 20, 2] > 200
    assert decode_frame({"jpeg": "data:image/jpeg;base64," + _jpeg_b64(img)}).shape == (90, 160, 3)
    assert decode_frame({"jpeg": "not a jpeg"}) is None
    assert decode_frame({}) is None
    assert decode_frame(None) is None


def test_hub_frames_read_and_latest():
    frames = HubFrames()
    push = lambda env: asyncio.run(frames.on_envelope(env))  # noqa: E731
    assert frames.latest() == (None, None)
    with pytest.raises(TimeoutError):
        frames.read(timeout=0.01)
    img = np.full((60, 80, 3), 128, np.uint8)
    push({"topic": "camera.frame", "ts": 5.0, "data": {"jpeg": _jpeg_b64(img)}})
    ts, frame = frames.read(timeout=0.1)
    assert ts == 5.0 and frame.shape == (60, 80, 3)
    with pytest.raises(TimeoutError):
        frames.read(timeout=0.01)  # nothing newer
    assert frames.latest()[0] == 5.0
    push({"topic": "camera.frame", "ts": 6.0, "data": {"jpeg": "rubbish"}})
    assert frames.bad == 1 and frames.latest()[0] == 5.0


def test_outline_and_client_ts_in_view_units_and_schema():
    t = Track(5, "bottle", [600, 300, 680, 420], 0.8, {"outline": [[600, 300], [680, 300], [700, 420], [-10, 420]]})
    s = build_state([t, Track(6, "cup", [10, 10, 50, 50], 0.9)], [], SHAPE, 3.0, client_ts=12345.6)
    assert s["client_ts"] == 12345.6
    assert s["objects"][0]["outline"] == [[0.469, 0.417], [0.531, 0.417], [0.547, 0.583], [0.0, 0.583]]
    assert "outline" not in s["objects"][1]
    assert "client_ts" not in build_state([], [], SHAPE, 3.0)
    if validate_envelope:
        assert validate_envelope(envelope(s)) == []


def test_hub_frames_remember_the_eye_timestamp_of_the_frame_read():
    frames = HubFrames()
    img = np.full((60, 80, 3), 128, np.uint8)
    asyncio.run(frames.on_envelope({"ts": 1.0, "data": {"jpeg": _jpeg_b64(img), "t": 500.5}}))
    frames.read(timeout=0.1)
    assert frames.read_client_ts == 500.5
    asyncio.run(frames.on_envelope({"ts": 2.0, "data": {"jpeg": _jpeg_b64(img)}}))
    frames.read(timeout=0.1)
    assert frames.read_client_ts is None
