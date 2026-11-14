"""Robot's-view snapshot endpoint with people blurred (T45, contract C8, whitepaper §7.7 and §11).

    GET :<VISION_HTTP_PORT>/snapshot.jpg  -> latest frame from the robot's camera, person/hand regions
                                             blurred, at most 1024 px wide, JPEG quality 80
    GET :<VISION_HTTP_PORT>/health        -> {"ok", "frame_age_s", "width", "height"}

Gemini gets this image when it composes a world (T74) and when it names a newly seen object (T76).

Blurring happens before anything is cropped or encoded, and images only ever live in memory: nothing is
written to disk.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Sequence

import cv2
import numpy as np

log = logging.getLogger("snapshot")

MAX_WIDTH = 1024
JPEG_QUALITY = 80
BLUR_PAD_FRACTION = 0.15   # grow each box a little so blur covers the edges of an arm or head
PIXELATE_BLOCK = 24


def blur_regions(frame: np.ndarray, boxes: Sequence[Sequence[float]]) -> np.ndarray:
    """A copy of `frame` with each box made unrecognisable (pixelate, then heavy blur)."""
    out = frame.copy()
    h, w = out.shape[:2]
    for b in boxes:
        x1, y1, x2, y2 = map(float, b[:4])
        px, py = (x2 - x1) * BLUR_PAD_FRACTION, (y2 - y1) * BLUR_PAD_FRACTION
        x1, y1 = max(0, int(x1 - px)), max(0, int(y1 - py))
        x2, y2 = min(w, int(np.ceil(x2 + px))), min(h, int(np.ceil(y2 + py)))
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        roi = out[y1:y2, x1:x2]
        small = cv2.resize(roi, (max(1, (x2 - x1) // PIXELATE_BLOCK), max(1, (y2 - y1) // PIXELATE_BLOCK)),
                           interpolation=cv2.INTER_AREA)
        roi = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_LINEAR)
        out[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (0, 0), sigmaX=max(3.0, (x2 - x1) / 20))
    return out


def fit_width(frame: np.ndarray, max_width: int = MAX_WIDTH) -> np.ndarray:
    h, w = frame.shape[:2]
    scale = min(1.0, max_width / w)
    return cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else frame


def make_snapshot(frame: np.ndarray, boxes: Sequence[Sequence[float]], max_width: int = MAX_WIDTH,
                  quality: int = JPEG_QUALITY) -> bytes:
    view = fit_width(blur_regions(frame, boxes), max_width)
    ok, buf = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return buf.tobytes()


class SnapshotServer:
    """Serves snapshots from callables, so it doesn't own the camera or the detectors.

    get_frame()   -> (ts, frame) or (None, None)      e.g. Camera.latest
    get_regions() -> list of [x1, y1, x2, y2] to blur  (giants and person detections)
    """

    def __init__(self, get_frame: Callable, get_regions: Callable, host: str = "127.0.0.1", port: int = 8080):
        self.get_frame = get_frame
        self.get_regions = get_regions
        self.httpd = ThreadingHTTPServer((host, port), self._make_handler())
        self.httpd.daemon_threads = True
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return self.httpd.server_address[1]

    def snapshot(self) -> bytes | None:
        ts, frame = self.get_frame()
        if frame is None:
            return None
        return make_snapshot(frame, self.get_regions() or [])

    def health(self) -> dict:
        ts, frame = self.get_frame()
        return {"ok": frame is not None, "frame_age_s": None if ts is None else round(time.time() - ts, 3),
                "width": None if frame is None else frame.shape[1],
                "height": None if frame is None else frame.shape[0]}

    def _make_handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def _send(self, code: int, body: bytes, ctype: str) -> None:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802 (http.server API)
                path = self.path.split("?", 1)[0]
                try:
                    if path == "/snapshot.jpg":
                        jpg = server.snapshot()
                        if jpg is None:
                            self._send(503, b"no frame yet\n", "text/plain")
                        else:
                            self._send(200, jpg, "image/jpeg")
                    elif path == "/health":
                        self._send(200, json.dumps(server.health()).encode(), "application/json")
                    else:
                        self._send(404, b"not found\n", "text/plain")
                except Exception:
                    log.exception("snapshot request failed")
                    self._send(500, b"error\n", "text/plain")

            def log_message(self, fmt, *args):  # keep request noise out of the logs
                log.debug(fmt, *args)

        return Handler

    def start(self) -> "SnapshotServer":
        self._thread = threading.Thread(target=self.httpd.serve_forever, name="snapshot", daemon=True)
        self._thread.start()
        log.info("snapshot server on :%d", self.port)
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
