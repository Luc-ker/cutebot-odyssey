"""Short-term re-identification (T40, contract C8).

When an object is hidden by a hand or the robot, or lifted and put back, the tracker (T39) gives it a
fresh ID. ReId maps that fresh ID back to the old one, so the object keeps its role in the world.

    reid = ReId(config, calib)
    tracks = reid.apply(tracker.update(dets, ts), ts, frame)   # frame is optional (colour histograms)

A lost ID is remembered for `OBJECT_GRACE_S` with its class, last position, size and a small HSV colour
histogram. A new track matches a remembered one when the classes are compatible, it is within
`max_dist_cm` of where the old one was last seen, and (if both histograms exist) the colours are
similar. Among several candidates the closest wins.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

import cv2
import numpy as np

from jetson.tracker import Track

MAX_DIST_CM = 10.0
MAX_DIST_PX = 60.0         # used when no calibration is available
MAX_SIZE_RATIO = 2.0       # a remembered cup does not come back twice as large
MIN_HIST_SIMILARITY = 0.5  # histogram correlation, -1..1

# Detector classes that are easily confused with one another from above.
_GROUPS = [
    {"cup", "bowl", "wine glass", "vase"},
    {"bottle", "vase", "wine glass"},
    {"book", "laptop", "keyboard"},
    {"backpack", "handbag", "suitcase"},
    {"cell phone", "remote", "mouse"},
    {"apple", "orange", "sports ball"},
]


def compatible(a: str, b: str) -> bool:
    if a == b or a == "object" or b == "object":
        return True
    return any(a in g and b in g for g in _GROUPS)


def colour_hist(frame: np.ndarray | None, bbox) -> np.ndarray | None:
    if frame is None:
        return None
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = (int(round(v)) for v in bbox)
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None
    hsv = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [12, 8], [0, 180, 0, 256])
    return cv2.normalize(hist, hist).flatten()


@dataclass
class _Memory:
    out_id: int
    cls: str
    pos: tuple[float, float]       # table units if calibrated, else pixels
    size: float                    # box diagonal in pixels
    hist: np.ndarray | None
    lost_at: float


class ReId:
    def __init__(self, config: dict | None = None, calib=None, grace_s: float | None = None,
                 max_dist_cm: float = MAX_DIST_CM, max_dist_px: float = MAX_DIST_PX):
        config = config or {}
        self.grace_s = grace_s if grace_s is not None else float(config.get("OBJECT_GRACE_S", 5.0))
        self.calib = calib
        self.table_cm = (float(config.get("TABLE_W_CM", 120.0)), float(config.get("TABLE_H_CM", 80.0)))
        self.max_dist_cm = max_dist_cm
        self.max_dist_px = max_dist_px
        self._map: dict[int, int] = {}          # tracker id -> output id
        self._map_seen: dict[int, float] = {}
        self._active: dict[int, _Memory] = {}   # output id -> latest info while visible
        self._lost: dict[int, _Memory] = {}     # output id -> memory while hidden

    def reset(self) -> None:
        self._map.clear()
        self._map_seen.clear()
        self._active.clear()
        self._lost.clear()

    # ------------------------------------------------------------------ geometry

    def _pos(self, bbox) -> tuple[float, float]:
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        if self.calib is not None:
            x, y = self.calib.to_table([cx, cy], clamp=False)
            return x, y
        return cx, cy

    def _close(self, a: tuple[float, float], b: tuple[float, float]) -> tuple[bool, float]:
        if self.calib is not None:
            d = math.hypot((a[0] - b[0]) * self.table_cm[0], (a[1] - b[1]) * self.table_cm[1])
            return d <= self.max_dist_cm, d
        d = math.hypot(a[0] - b[0], a[1] - b[1])
        return d <= self.max_dist_px, d

    # ------------------------------------------------------------------ main

    def _match(self, cls: str, pos, size: float, hist) -> int | None:
        best, best_d = None, math.inf
        for out_id, m in self._lost.items():
            if not compatible(cls, m.cls):
                continue
            ok, d = self._close(pos, m.pos)
            if not ok:
                continue
            if m.size > 0 and size > 0 and max(size / m.size, m.size / size) > MAX_SIZE_RATIO:
                continue
            if hist is not None and m.hist is not None:
                if cv2.compareHist(hist.astype(np.float32), m.hist.astype(np.float32),
                                   cv2.HISTCMP_CORREL) < MIN_HIST_SIMILARITY:
                    continue
            if d < best_d:
                best, best_d = out_id, d
        return best

    def apply(self, tracks: list[Track], ts: float, frame: np.ndarray | None = None) -> list[Track]:
        # Forget memories past the grace period.
        self._lost = {k: m for k, m in self._lost.items() if ts - m.lost_at <= self.grace_s}

        out: list[Track] = []
        visible: dict[int, _Memory] = {}
        for t in tracks:
            pos = self._pos(t.bbox)
            size = math.hypot(t.bbox[2] - t.bbox[0], t.bbox[3] - t.bbox[1])
            hist = colour_hist(frame, t.bbox)
            out_id = self._map.get(t.id)
            if out_id is None:
                out_id = self._match(t.cls, pos, size, hist)
                if out_id is None or out_id in visible:
                    out_id = t.id
                self._map[t.id] = out_id
            self._lost.pop(out_id, None)
            self._map_seen[t.id] = ts
            prev = self._active.get(out_id)
            if hist is None and prev is not None:
                hist = prev.hist
            visible[out_id] = _Memory(out_id, t.cls, pos, size, hist, ts)
            out.append(dataclasses.replace(t, id=out_id))

        # IDs visible last frame but not now become memories.
        for out_id, m in self._active.items():
            if out_id not in visible:
                m.lost_at = ts
                self._lost[out_id] = m
        self._active = visible

        # Drop tracker-id mappings that have been unused for longer than the grace period.
        stale = [k for k, seen in self._map_seen.items() if ts - seen > self.grace_s]
        for k in stale:
            self._map.pop(k, None)
            self._map_seen.pop(k, None)
        return out
