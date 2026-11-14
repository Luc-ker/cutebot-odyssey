"""Hand and person ("giant") detection in the robot's view (T43, contract C8, whitepaper §7.10).

    giants = GiantDetector()
    giants.detect(frame, persons=None) -> list[{"bbox", "kind", "edge"}]

The camera rides on the robot and moves all the time, so there is no fixed background to subtract.
A giant is either

- a **person** detection from the object model (T38), or
- a **hand**: a large skin-coloured blob that reaches into the frame from the top or a side. From five
  centimetres up, a hand reaching down to the table comes in from above; the table itself fills the bottom
  of the frame, so a blob touching the bottom edge must also touch the top to count (a wooden table can look
  skin-coloured).

`edge` is the frame edge the giant reaches in from ("top", "left", "right" or "bottom").

Privacy (§11): only blob shapes and colour ranges are used. No face detection, nothing is cropped or stored.
"""
from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np

WORK_WIDTH = 320              # downscale for speed
MIN_AREA_FRACTION = 0.04      # of the frame: smaller skin blobs are noise or far away
MAX_AREA_FRACTION = 0.85      # nearly the whole frame skin-coloured: lighting, not a hand
EDGE_BAND = 3                 # px at WORK_WIDTH that count as touching an edge
PERSON_CONF = 0.4

# Skin in YCrCb (a common, lighting-tolerant range).
CR_RANGE = (135, 175)
CB_RANGE = (85, 130)
Y_MIN = 40


def skin_mask(frame: np.ndarray) -> tuple[np.ndarray, float]:
    """Binary skin mask at the working size, and the scale used."""
    scale = min(1.0, WORK_WIDTH / frame.shape[1])
    small = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else frame
    ycrcb = cv2.cvtColor(cv2.GaussianBlur(small, (5, 5), 0), cv2.COLOR_BGR2YCrCb)
    lo = np.array([Y_MIN, CR_RANGE[0], CB_RANGE[0]], np.uint8)
    hi = np.array([255, CR_RANGE[1], CB_RANGE[1]], np.uint8)
    mask = cv2.inRange(ycrcb, lo, hi)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    return mask, scale


def _edges_touched(x: int, y: int, w: int, h: int, fw: int, fh: int) -> set[str]:
    edges = set()
    if y <= EDGE_BAND:
        edges.add("top")
    if y + h >= fh - EDGE_BAND:
        edges.add("bottom")
    if x <= EDGE_BAND:
        edges.add("left")
    if x + w >= fw - EDGE_BAND:
        edges.add("right")
    return edges


def _entry_edge(edges: set[str]) -> str | None:
    """The edge a hand reaches in from, or None if this blob is not a giant."""
    if "top" in edges:
        return "top"
    if "bottom" in edges:
        return None  # most likely the table surface
    for e in ("left", "right"):
        if e in edges:
            return e
    return None


def _nearest_edge(bbox: Sequence[float], fw: int, fh: int) -> str:
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    d = {"left": cx, "right": fw - cx, "top": cy, "bottom": fh - cy}
    return min(d, key=d.get)


class GiantDetector:
    def __init__(self, min_area_fraction: float = MIN_AREA_FRACTION):
        self.min_area_fraction = min_area_fraction

    def reset(self) -> None:
        """Nothing to forget: detection is per frame. Kept so the pipeline can reset every part alike."""

    def detect(self, frame: np.ndarray, persons: Sequence | None = None) -> list[dict]:
        fh, fw = frame.shape[:2]
        mask, scale = skin_mask(frame)
        mh, mw = mask.shape[:2]
        area = mh * mw
        giants = []
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        for i in range(1, n):
            a = stats[i, cv2.CC_STAT_AREA]
            if a < self.min_area_fraction * area or a > MAX_AREA_FRACTION * area:
                continue
            x, y, w, h = (int(v) for v in stats[i, :4])
            edge = _entry_edge(_edges_touched(x, y, w, h, mw, mh))
            if edge is None:
                continue
            bbox = [x / scale, y / scale, (x + w) / scale, (y + h) / scale]
            giants.append({"bbox": [float(v) for v in bbox], "kind": "hand", "edge": edge})

        for p in persons or []:
            if getattr(p, "conf", 1.0) < PERSON_CONF:
                continue
            pb = [float(v) for v in getattr(p, "bbox", p)[:4]]
            overlapping = [g for g in giants if _overlap(pb, g["bbox"]) > 0.3]
            if overlapping:
                for g in overlapping:  # the detector is sure it's a person: trust it
                    g["kind"] = "person"
                continue
            giants.append({"bbox": pb, "kind": "person", "edge": _nearest_edge(pb, fw, fh)})
        return giants


def _overlap(a, b) -> float:
    """Intersection over the smaller box."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return inter / smaller if smaller > 0 else 0.0
