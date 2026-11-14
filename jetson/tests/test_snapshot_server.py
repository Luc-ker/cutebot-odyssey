import json
import os
import time
import urllib.request

import cv2
import numpy as np
import pytest

from jetson.calibration import Calibration
from jetson.snapshot_server import SnapshotServer, blur_regions, make_snapshot


def noisy_frame(w=1280, h=720, seed=0):
    """High-variance texture everywhere, so blurring is measurable."""
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, (h, w, 3), dtype=np.uint8)


def decode(jpg: bytes) -> np.ndarray:
    return cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)


def test_blurred_region_has_low_variance():
    frame = noisy_frame()
    box = [400, 200, 700, 500]
    out = blur_regions(frame, [box])
    assert frame[250:450, 450:650].std() > 60
    assert out[250:450, 450:650].std() < 15
    assert np.array_equal(out[600:700, 1000:1200], frame[600:700, 1000:1200])  # rest untouched


def test_snapshot_jpeg_region_over_giant_is_blurred_identity_calib():
    frame = noisy_frame(1024, 576)
    jpg = make_snapshot(frame, [[100, 100, 400, 400]], None)
    img = decode(jpg)
    assert img.shape[1] <= 1024
    assert img[150:350, 150:350].std() < 15
    assert img[450:550, 600:900].std() > 40


def test_snapshot_is_cropped_to_table_and_capped_at_1024():
    frame = noisy_frame(1920, 1080)
    calib = Calibration([[100, 100], [1820, 100], [1820, 1000], [100, 1000]], (1920, 1080))
    img = decode(make_snapshot(frame, [], calib, aspect=1.5))
    assert img.shape[1] == 1024 and img.shape[0] == round(1024 / 1.5)


def test_http_server_blurs_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = set(os.listdir(tmp_path))
    frame = noisy_frame()
    box = [500, 250, 800, 500]
    calib = Calibration([[0, 0], [1280, 0], [1280, 720], [0, 720]])
    srv = SnapshotServer(lambda: (time.time(), frame), lambda: [box], calib,
                         {"TABLE_W_CM": 128, "TABLE_H_CM": 72}, host="127.0.0.1", port=0).start()
    try:
        base = f"http://127.0.0.1:{srv.port}"
        with urllib.request.urlopen(base + "/snapshot.jpg", timeout=5) as r:
            assert r.headers["Content-Type"] == "image/jpeg"
            img = decode(r.read())
        assert img.shape[:2] == (576, 1024)  # 1280x720 scaled to 1024 wide
        s = 1024 / 1280
        assert img[int(300 * s):int(450 * s), int(550 * s):int(750 * s)].std() < 15
        with urllib.request.urlopen(base + "/health", timeout=5) as r:
            h = json.loads(r.read())
        assert h["ok"] is True and h["width"] == 1280
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + "/nope", timeout=5)
    finally:
        srv.stop()
    assert set(os.listdir(tmp_path)) == before


def test_no_frame_yet_is_503():
    srv = SnapshotServer(lambda: (None, None), lambda: [], None, host="127.0.0.1", port=0).start()
    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"http://127.0.0.1:{srv.port}/snapshot.jpg", timeout=5)
        assert e.value.code == 503
    finally:
        srv.stop()
