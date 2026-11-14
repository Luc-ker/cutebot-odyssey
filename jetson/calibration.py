"""Overhead camera pixel <-> table coordinates (T37, contracts C1/C8).

A homography maps camera pixels `[u, v]` to normalised table coords `[x, y]` (0..1, origin at the table's
top-left as seen from the camera, y down). It is built from the four table corners clicked in
`jetson/calibrate_tool.py` (TL, TR, BR, BL) and saved to `jetson/calibration.json`.

    calib = Calibration.load("jetson/calibration.json")
    calib.to_table([u, v]) -> [x, y]   clamped to [0, 1] (pass clamp=False for the raw value)
    calib.to_pixel([x, y]) -> [u, v]
    calib.contains([u, v]) -> bool     is the pixel on the table?
    calib.edge_of([u, v])  -> "top" | "bottom" | "left" | "right" | None
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

DEFAULT_PATH = Path(__file__).resolve().parent / "calibration.json"
UNIT_SQUARE = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])


def _apply(h: np.ndarray, pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(pts, h).reshape(-1, 2)


class Calibration:
    def __init__(self, corners_px: Sequence[Sequence[float]], image_size: Sequence[int] | None = None):
        """`corners_px`: table corners in pixels, in order TL, TR, BR, BL."""
        self.corners_px = np.float32(corners_px).reshape(4, 2)
        self.image_size = tuple(image_size) if image_size else None
        self.H = cv2.getPerspectiveTransform(self.corners_px, UNIT_SQUARE).astype(np.float64)
        self.H_inv = np.linalg.inv(self.H)

    # ------------------------------------------------------------------ construction / persistence

    @classmethod
    def identity(cls, width: int, height: int) -> "Calibration":
        """The whole frame is the table (a fallback before calibrating)."""
        return cls([[0, 0], [width, 0], [width, height], [0, height]], (width, height))

    @classmethod
    def load(cls, path: str | Path = DEFAULT_PATH) -> "Calibration":
        data = json.loads(Path(path).read_text())
        return cls(data["corners_px"], data.get("image_size"))

    def save(self, path: str | Path = DEFAULT_PATH) -> None:
        Path(path).write_text(json.dumps({
            "corners_px": self.corners_px.tolist(),
            "image_size": list(self.image_size) if self.image_size else None,
            "H": self.H.tolist(),
            "order": "TL, TR, BR, BL",
        }, indent=2))

    # ------------------------------------------------------------------ mapping

    def to_table_raw(self, px: Sequence[float]) -> list[float]:
        x, y = _apply(self.H, np.asarray(px, dtype=np.float64))[0]
        return [float(x), float(y)]

    def to_table(self, px: Sequence[float], clamp: bool = True) -> list[float]:
        x, y = self.to_table_raw(px)
        if clamp:
            x, y = min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)
        return [x, y]

    def to_table_many(self, pts: np.ndarray, clamp: bool = True) -> np.ndarray:
        out = _apply(self.H, pts)
        return np.clip(out, 0.0, 1.0) if clamp else out

    def to_pixel(self, xy: Sequence[float]) -> list[float]:
        u, v = _apply(self.H_inv, np.asarray(xy, dtype=np.float64))[0]
        return [float(u), float(v)]

    def contains(self, px: Sequence[float]) -> bool:
        x, y = self.to_table_raw(px)
        return 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0

    def edge_of(self, px: Sequence[float], margin: float | None = None) -> str | None:
        """The table edge a pixel is beyond, or else nearest to.

        With `margin` (table units), a point further inside the table than `margin` from every edge
        returns None."""
        x, y = self.to_table_raw(px)
        if not (np.isfinite(x) and np.isfinite(y)):
            return None
        # Distance *inside* each edge; negative means beyond it.
        inside = {"left": x, "right": 1.0 - x, "top": y, "bottom": 1.0 - y}
        edge = min(inside, key=inside.get)
        if margin is not None and inside[edge] > margin:
            return None
        return edge

    # ------------------------------------------------------------------ helpers for other modules

    def polygon(self) -> np.ndarray:
        """Table outline in pixels as an int32 contour (TL, TR, BR, BL)."""
        return self.corners_px.reshape(-1, 1, 2).astype(np.int32)

    def mask(self, shape: Sequence[int]) -> np.ndarray:
        """uint8 mask (255 on the table) for a frame of `shape` (h, w[, c])."""
        m = np.zeros(tuple(shape[:2]), np.uint8)
        cv2.fillConvexPoly(m, self.polygon(), 255)
        return m

    def box_overlaps_table(self, bbox: Sequence[float]) -> bool:
        """True if a pixel box [x1, y1, x2, y2] overlaps the table polygon at all."""
        x1, y1, x2, y2 = map(float, bbox)
        box = np.float32([[x1, y1], [x2, y1], [x2, y2], [x1, y2]])
        area, _ = cv2.intersectConvexConvex(box, self.corners_px)
        return area > 0
