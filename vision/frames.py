"""Frames from the phone on the robot, received through the hub (contract C3 `camera.frame`).

The phone streams its camera to the eye page over WebRTC (T25, T26). The eye page samples that stream a few
times a second and publishes each sample as a JPEG on `camera.frame` (`web/eye/frames.js`). This turns those
messages back into frames with the same interface as `Camera`, so the pipeline doesn't care where frames
come from:

    frames = HubFrames()
    hub.sub("camera.frame", frames.on_envelope)
    ts, frame = frames.read(timeout=5.0)    # blocks until a frame newer than the last read()
    ts, frame = frames.latest()             # returns at once; (None, None) before the first frame
    frames.read_client_ts                   # the eye page's `t` for the frame read() last returned, or None

Only the latest frame is kept, in memory. Nothing is written to disk.
"""
from __future__ import annotations

import base64
import binascii
import logging
import threading
import time
from collections import deque

import cv2
import numpy as np

log = logging.getLogger("frames")


def decode_frame(data: dict) -> np.ndarray | None:
    """`camera.frame` data -> BGR image, or None if it isn't a decodable JPEG."""
    b64 = data.get("jpeg") if isinstance(data, dict) else None
    if not isinstance(b64, str) or not b64:
        return None
    if b64.startswith("data:"):
        b64 = b64.split(",", 1)[-1]
    try:
        raw = base64.b64decode(b64, validate=False)
    except (binascii.Error, ValueError):
        return None
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    return img if img is not None and img.size else None


class HubFrames:
    def __init__(self):
        self._cond = threading.Condition()
        self._frame: np.ndarray | None = None
        self._ts: float | None = None
        self._client_ts: float | None = None
        self.read_client_ts: float | None = None
        self._seq = 0
        self._read_seq = 0
        self._stamps: deque[float] = deque(maxlen=30)
        self.bad = 0

    def push(self, frame: np.ndarray, ts: float | None = None, client_ts: float | None = None) -> None:
        with self._cond:
            self._frame, self._ts = frame, float(ts if ts is not None else time.time())
            self._client_ts = client_ts
            self._seq += 1
            self._stamps.append(time.monotonic())
            self._cond.notify_all()

    async def on_envelope(self, env: dict) -> None:
        frame = decode_frame(env.get("data") or {})
        if frame is None:
            self.bad += 1
            if self.bad in (1, 10, 100):
                log.warning("undecodable camera.frame (%d so far)", self.bad)
            return
        ts = env.get("ts")
        t = (env.get("data") or {}).get("t")
        client_ts = float(t) if isinstance(t, (int, float)) and not isinstance(t, bool) else None
        self.push(frame, ts if isinstance(ts, (int, float)) else None, client_ts)

    def read(self, timeout: float | None = 5.0) -> tuple[float, np.ndarray]:
        with self._cond:
            ok = self._cond.wait_for(lambda: self._seq > self._read_seq, timeout)
            if not ok:
                raise TimeoutError("no new camera.frame")
            self._read_seq = self._seq
            self.read_client_ts = self._client_ts
            return self._ts, self._frame

    def latest(self) -> tuple[float | None, np.ndarray | None]:
        with self._cond:
            return self._ts, self._frame

    def clear(self) -> None:
        with self._cond:
            self._frame, self._ts = None, None

    @property
    def fps(self) -> float:
        s = self._stamps
        if len(s) < 2 or s[-1] == s[0]:
            return 0.0
        return (len(s) - 1) / (s[-1] - s[0])

    def stop(self) -> None:
        with self._cond:
            self._cond.notify_all()
