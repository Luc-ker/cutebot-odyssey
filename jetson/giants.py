"""Hand and person ("giant") detection (T43, contract C8, whitepaper §7.10).

    giants = GiantDetector(calib)
    giants.learn(frame)                                     # call with empty-table frames (start, reset)
    giants.detect(frame, calib=None, persons=None) -> list[{"bbox", "kind", "edge"}]

A giant is a foreground blob (difference against the learned empty-table background), or a "person"
detection from T38, that touches or crosses a table edge. Objects resting on the table don't touch an
edge, so they are never giants. `kind` is "hand" if the blob is mostly inside the table, else "person".
`edge` is the table edge it comes in from.

Privacy (§11): only blob shapes are used. No face detection, nothing is cropped or stored.
"""
from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np

LEARN_FRAMES = 15            # frames averaged into the background before detecting
DIFF_THRESHOLD = 35          # grey-level difference that counts as foreground
MIN_AREA_FRACTION = 0.004    # of the table area
EDGE_BAND_PX = 6             # a blob within this many px of the table outline "touches" the edge
WORK_WIDTH = 640             # downscale for speed
BG_ADAPT = 0.01              # slow background update where nothing is happening (lighting drift)


class GiantDetector:
    def __init__(self, calib=None, learn_frames: int = LEARN_FRAMES, diff_threshold: int = DIFF_THRESHOLD):
        self.calib = calib
        self.learn_frames = learn_frames
        self.diff_threshold = diff_threshold
        self._acc: np.ndarray | None = None
        self._n = 0
        self.background: np.ndarray | None = None
        self._masks_for: tuple | None = None

    # ------------------------------------------------------------------ background

    def reset(self) -> None:
        """Forget the background; the next `learn_frames` frames are learned again."""
        self._acc, self._n, self.background = None, 0, None

    @property
    def ready(self) -> bool:
        return self.background is not None

    def _prep(self, frame: np.ndarray) -> tuple[np.ndarray, float]:
        scale = min(1.0, WORK_WIDTH / frame.shape[1])
        small = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else frame
        gray = small if small.ndim == 2 else cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray, (5, 5), 0).astype(np.float32), scale

    def learn(self, frame: np.ndarray) -> bool:
        """Add an empty-table frame to the background. Returns True once the background is ready."""
        gray, _ = self._prep(frame)
        if self._acc is None or self._acc.shape != gray.shape:
            self._acc, self._n = np.zeros_like(gray), 0
        self._acc += gray
        self._n += 1
        if self._n >= self.learn_frames:
            self.background = self._acc / self._n
        return self.ready

    # ------------------------------------------------------------------ detection

    def _table_masks(self, calib, shape: tuple[int, int], scale: float):
        key = (id(calib), shape, scale)
        if self._masks_for != key:
            h, w = shape
            table = np.zeros((h, w), np.uint8)
            if calib is None:
                poly = np.int32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
            else:
                poly = np.int32(np.round(calib.corners_px * scale))
            cv2.fillConvexPoly(table, poly.reshape(-1, 1, 2), 255)
            band = np.zeros((h, w), np.uint8)
            cv2.polylines(band, [poly.reshape(-1, 1, 2)], True, 255, thickness=2 * EDGE_BAND_PX)
            self._table, self._band, self._table_area = table, band, max(1, int(np.count_nonzero(table)))
            self._masks_for = key
        return self._table, self._band, self._table_area

    def _edge_for(self, calib, pts_px: np.ndarray, frame_shape) -> str:
        cx, cy = pts_px.mean(axis=0)
        if calib is not None:
            return calib.edge_of([cx, cy])
        h, w = frame_shape[:2]
        d = {"left": cx, "right": w - cx, "top": cy, "bottom": h - cy}
        return min(d, key=d.get)

    def detect(self, frame: np.ndarray, calib=None, persons: Sequence | None = None) -> list[dict]:
        calib = calib if calib is not None else self.calib
        if not self.ready:
            self.learn(frame)
            return []
        gray, scale = self._prep(frame)
        table, band, table_area = self._table_masks(calib, gray.shape, scale)

        diff = cv2.absdiff(gray, self.background)
        fg = (diff > self.diff_threshold).astype(np.uint8) * 255
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        # Let the background follow slow lighting changes where nothing is in front of it.
        still = fg == 0
        self.background[still] += BG_ADAPT * (gray[still] - self.background[still])

        n, labels, stats, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
        giants = []
        min_area = MIN_AREA_FRACTION * table_area
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] < min_area:
                continue
            blob = labels == i
            inside = np.count_nonzero(blob & (table > 0))
            if inside == 0:
                continue  # entirely off the table
            outside = np.count_nonzero(blob & (table == 0))
            touching = blob & (band > 0)
            if outside == 0 and not touching.any():
                continue  # resting on the table: an object, not a giant
            ys, xs = np.nonzero(touching if touching.any() else blob)
            edge_pts = np.stack([xs, ys], axis=1).astype(np.float64) / scale
            x, y, w, h = stats[i, :4]
            bbox = [x / scale, y / scale, (x + w) / scale, (y + h) / scale]
            kind = "hand" if inside / (inside + outside) >= 0.5 else "person"
            giants.append({"bbox": [float(v) for v in bbox], "kind": kind,
                           "edge": self._edge_for(calib, edge_pts, frame.shape)})

        for p in persons or []:
            pb = list(getattr(p, "bbox", p))
            if calib is not None and not calib.box_overlaps_table(pb):
                continue
            if any(_overlap(pb, g["bbox"]) > 0.3 for g in giants):
                for g in giants:  # the detector is sure it's a person: trust it
                    if _overlap(pb, g["bbox"]) > 0.3:
                        g["kind"] = "person"
                continue
            centre = np.array([[(pb[0] + pb[2]) / 2, (pb[1] + pb[3]) / 2]])
            giants.append({"bbox": [float(v) for v in pb], "kind": "person",
                           "edge": self._edge_for(calib, centre, frame.shape)})
        return giants


def _overlap(a, b) -> float:
    """Intersection over the smaller box."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return inter / smaller if smaller > 0 else 0.0
