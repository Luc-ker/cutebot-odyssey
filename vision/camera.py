"""Local camera capture, for development and testing without the phone (T36, contract C8).

In the game the frames come from the phone on the robot, through the eye page and the hub (`vision/frames.py`).
This reads a camera plugged into this machine, or a recorded clip, instead:

    cam = Camera(config)                 # camera 0 (V4L2 on Linux)
    cam = Camera(config, file="clip.mp4") # a recorded clip instead (looped, paced at the clip's fps)
    ts, frame = cam.read()               # blocks until a frame newer than the last read()
    ts, frame = cam.latest()             # returns at once; (None, None) before the first frame
    cam.fps                              # measured capture rate
    cam.stop()

A background thread keeps only the latest frame. If the camera disconnects it is reopened automatically.
Exposure and white balance are fixed (manual) where the driver supports it, so detection stays stable.

Run `python -m vision.camera [--index 0 | --file clip.mp4]` to print the fps.
"""
from __future__ import annotations

import argparse
import logging
import platform
import threading
import time
from collections import deque

import cv2
import numpy as np

log = logging.getLogger("camera")

DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS = 30
REOPEN_DELAY_S = 1.0


class Camera:
    def __init__(self, config: dict | None = None, index: int | str | None = None, file: str | None = None,
                 width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT, fps: int = DEFAULT_FPS,
                 exposure: float | None = None, loop: bool = True, start: bool = True):
        config = config or {}
        self.index = index if index is not None else config.get("CAMERA_INDEX", 0)
        self.file = file
        self.width, self.height, self.target_fps = width, height, fps
        self.exposure = exposure if exposure is not None else config.get("CAMERA_EXPOSURE")
        self.loop = loop
        self._cond = threading.Condition()
        self._frame: np.ndarray | None = None
        self._ts: float | None = None
        self._seq = 0
        self._read_seq = 0
        self._stamps: deque[float] = deque(maxlen=60)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.eof = False  # set when a non-looping file ends
        if start:
            self.start()

    # ------------------------------------------------------------------ public

    def start(self) -> "Camera":
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="camera", daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def read(self, timeout: float | None = 5.0) -> tuple[float, np.ndarray]:
        """Block until a frame newer than the one returned by the previous read()."""
        with self._cond:
            ok = self._cond.wait_for(lambda: self._seq > self._read_seq or self._stop.is_set() or self.eof,
                                     timeout)
            if not ok or self._seq <= self._read_seq:
                raise TimeoutError("no new camera frame")
            self._read_seq = self._seq
            return self._ts, self._frame

    def latest(self) -> tuple[float | None, np.ndarray | None]:
        """The most recent frame, without waiting."""
        with self._cond:
            return self._ts, self._frame

    @property
    def fps(self) -> float:
        s = self._stamps
        if len(s) < 2 or s[-1] == s[0]:
            return 0.0
        return (len(s) - 1) / (s[-1] - s[0])

    def __enter__(self) -> "Camera":
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    # ------------------------------------------------------------------ capture thread

    def _open(self) -> cv2.VideoCapture | None:
        if self.file:
            cap = cv2.VideoCapture(self.file)
        elif platform.system() == "Linux":
            cap = cv2.VideoCapture(int(self.index) if str(self.index).isdigit() else self.index, cv2.CAP_V4L2)
        else:
            cap = cv2.VideoCapture(int(self.index) if str(self.index).isdigit() else self.index)
        if not cap.isOpened():
            cap.release()
            return None
        if not self.file:
            self._configure(cap)
        return cap

    def _configure(self, cap: cv2.VideoCapture) -> None:
        # MJPG lets USB 2 cameras reach 720p30; then size, rate, and manual exposure / white balance.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  # privacy-ok: sets the capture codec; nothing is written
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.target_fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # V4L2: 1 = manual, 3 = aperture priority (auto)
        if self.exposure is not None:
            cap.set(cv2.CAP_PROP_EXPOSURE, float(self.exposure))
        cap.set(cv2.CAP_PROP_AUTO_WB, 0)
        log.info("camera %s opened at %dx%d @ %.0f fps", self.index,
                 cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT), cap.get(cv2.CAP_PROP_FPS))

    def _publish(self, frame: np.ndarray) -> None:
        ts = time.time()
        with self._cond:
            self._frame, self._ts = frame, ts
            self._seq += 1
            self._stamps.append(time.monotonic())
            self._cond.notify_all()

    def _loop(self) -> None:
        cap = None
        file_period = None
        next_due = time.monotonic()
        while not self._stop.is_set():
            if cap is None:
                cap = self._open()
                if cap is None:
                    log.warning("camera %s not available; retrying", self.file or self.index)
                    self._stop.wait(REOPEN_DELAY_S)
                    continue
                if self.file:
                    clip_fps = cap.get(cv2.CAP_PROP_FPS) or self.target_fps
                    file_period = 1.0 / (clip_fps if 1 <= clip_fps <= 240 else self.target_fps)
                    next_due = time.monotonic()
            ok, frame = cap.read()
            if not ok or frame is None:
                if self.file and self.loop:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = cap.read()
                if not ok or frame is None:
                    cap.release()
                    cap = None
                    if self.file and not self.loop:
                        self.eof = True
                        with self._cond:
                            self._cond.notify_all()
                        break
                    log.warning("camera read failed; reopening")
                    self._stop.wait(REOPEN_DELAY_S)
                    continue
            if file_period:  # pace a clip like a live camera
                next_due += file_period
                delay = next_due - time.monotonic()
                if delay > 0:
                    self._stop.wait(delay)
                else:
                    next_due = time.monotonic()
            self._publish(frame)
        if cap is not None:
            cap.release()


def main() -> None:
    p = argparse.ArgumentParser(description="Print camera fps")
    p.add_argument("--index", default=0)
    p.add_argument("--file")
    p.add_argument("--seconds", type=float, default=10)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO)
    with Camera(index=args.index, file=args.file) as cam:
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            ts, frame = cam.read()
            print(f"\r{frame.shape[1]}x{frame.shape[0]}  {cam.fps:5.1f} fps", end="", flush=True)
        print()


if __name__ == "__main__":
    main()
