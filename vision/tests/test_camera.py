import time

import cv2
import numpy as np
import pytest

from vision.camera import Camera


@pytest.fixture
def clip(tmp_path):
    """A 1-second 30 fps MJPG clip with a moving square."""
    path = str(tmp_path / "clip.avi")
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 30, (320, 240))
    assert w.isOpened()
    for i in range(30):
        f = np.full((240, 320, 3), 40, np.uint8)
        cv2.rectangle(f, (10 + i * 5, 100), (40 + i * 5, 130), (0, 255, 0), -1)
        w.write(f)
    w.release()
    return path


def test_read_returns_increasing_timestamps(clip):
    with Camera(file=clip) as cam:
        stamps = [cam.read(timeout=3)[0] for _ in range(10)]
    assert all(b > a for a, b in zip(stamps, stamps[1:]))


def test_read_returns_new_frames_only(clip):
    with Camera(file=clip) as cam:
        ts1, f1 = cam.read(timeout=3)
        ts2, f2 = cam.read(timeout=3)
    assert ts2 > ts1 and f1.shape == (240, 320, 3)


def test_latest_never_blocks(clip):
    cam = Camera(file=clip, start=False)
    t0 = time.perf_counter()
    assert cam.latest() == (None, None)  # before any frame
    assert time.perf_counter() - t0 < 0.01
    cam.start()
    try:
        cam.read(timeout=3)
        for _ in range(50):
            t0 = time.perf_counter()
            ts, frame = cam.latest()
            assert time.perf_counter() - t0 < 0.01
            assert frame is not None
    finally:
        cam.stop()


def test_file_is_paced_and_fps_measured(clip):
    with Camera(file=clip) as cam:
        for _ in range(20):
            cam.read(timeout=3)
        assert 20 <= cam.fps <= 40  # paced near the clip's 30 fps


def test_clip_loops(clip):
    with Camera(file=clip) as cam:
        for _ in range(45):  # more frames than the 30-frame clip
            cam.read(timeout=3)
        assert not cam.eof


def test_missing_camera_does_not_raise(tmp_path):
    with Camera(file=str(tmp_path / "nope.avi")) as cam:
        assert cam.latest() == (None, None)
        with pytest.raises(TimeoutError):
            cam.read(timeout=0.2)
