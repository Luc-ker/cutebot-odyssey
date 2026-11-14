"""Persistent-ID object tracker (T39, contract C8).

ByteTrack-style, no extra dependencies:
- each track has a constant-velocity Kalman filter over its box centre and size;
- association runs twice per frame: high-confidence detections first, then low-confidence ones
  against the tracks still unmatched (this is what keeps a briefly faint object alive);
- matching is greedy on IoU between the *predicted* box and the detection, with a penalty for a
  class change, so two objects crossing keep their own IDs.

    tracker = Tracker()
    tracks = tracker.update(detections, ts) -> list[Track{id, cls, bbox, conf}]

IDs are integers, never reused in a session. A track's class is the majority vote of its last
`CLASS_HISTORY` detections. Only tracks seen in this frame are returned (lost tracks are kept
internally for `max_lost_s` so they can be re-matched; longer gaps are T40's job).
"""
from __future__ import annotations

import itertools
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

HIGH_CONF = 0.5
MATCH_IOU = 0.2
LOW_MATCH_IOU = 0.4
CLASS_HISTORY = 15
CLASS_CHANGE_PENALTY = 0.3


@dataclass
class Track:
    id: int
    cls: str
    bbox: list[float]
    conf: float
    extra: dict = field(default_factory=dict)

    @property
    def centre(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return (x1 + x2) / 2, (y1 + y2) / 2


def iou(a: Sequence[float], b: Sequence[float]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / area if area > 0 else 0.0


class _Kalman:
    """Constant-velocity filter on [cx, cy, w, h] with velocities on cx, cy."""

    def __init__(self, bbox: Sequence[float]):
        x1, y1, x2, y2 = bbox
        self.x = np.array([(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1, 0.0, 0.0])
        self.P = np.diag([10.0, 10.0, 10.0, 10.0, 100.0, 100.0])
        self.H = np.zeros((4, 6))
        self.H[:4, :4] = np.eye(4)
        self.R = np.diag([4.0, 4.0, 16.0, 16.0])

    def predict(self, dt: float) -> None:
        F = np.eye(6)
        F[0, 4] = F[1, 5] = dt
        q = max(dt, 1e-3)
        Q = np.diag([1.0, 1.0, 4.0, 4.0, 50.0, 50.0]) * q
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + Q

    def update(self, bbox: Sequence[float]) -> None:
        x1, y1, x2, y2 = bbox
        z = np.array([(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1])
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ self.H) @ self.P

    def bbox(self) -> list[float]:
        cx, cy, w, h = self.x[:4]
        w, h = max(w, 1.0), max(h, 1.0)
        return [float(cx - w / 2), float(cy - h / 2), float(cx + w / 2), float(cy + h / 2)]


class _State:
    def __init__(self, det, ts: float, track_id: int):
        self.id = track_id
        self.kf = _Kalman(det.bbox)
        self.classes: deque[str] = deque([det.cls], maxlen=CLASS_HISTORY)
        self.conf = det.conf
        self.bbox = list(det.bbox)
        self.last_seen = ts
        self.last_ts = ts
        self.hits = 1

    @property
    def cls(self) -> str:
        counts = Counter(self.classes)
        best = max(counts.values())
        # Ties go to the most recent of the tied classes.
        for c in reversed(self.classes):
            if counts[c] == best:
                return c
        return self.classes[-1]

    def predict(self, ts: float) -> None:
        self.kf.predict(max(0.0, ts - self.last_ts))
        self.last_ts = ts

    def update(self, det, ts: float) -> None:
        self.kf.update(det.bbox)
        self.bbox = list(det.bbox)
        self.classes.append(det.cls)
        self.conf = det.conf
        self.last_seen = ts
        self.hits += 1


class Tracker:
    def __init__(self, max_lost_s: float = 1.0, high_conf: float = HIGH_CONF, min_hits: int = 1):
        self.max_lost_s = max_lost_s
        self.high_conf = high_conf
        self.min_hits = min_hits
        self._tracks: list[_State] = []
        self._ids = itertools.count(1)

    def reset(self) -> None:
        """Forget all tracks (IDs still never repeat)."""
        self._tracks.clear()

    def _associate(self, tracks: list[_State], dets: list, min_iou: float) -> tuple[list, list, list]:
        pairs = []
        for ti, t in enumerate(tracks):
            pred = t.kf.bbox()
            for di, d in enumerate(dets):
                score = iou(pred, d.bbox)
                if score <= 0:
                    continue
                if d.cls != t.cls:
                    score -= CLASS_CHANGE_PENALTY
                if score >= min_iou:
                    pairs.append((score, ti, di))
        pairs.sort(reverse=True)
        used_t, used_d, matches = set(), set(), []
        for _, ti, di in pairs:
            if ti in used_t or di in used_d:
                continue
            used_t.add(ti)
            used_d.add(di)
            matches.append((tracks[ti], dets[di]))
        return (matches,
                [t for i, t in enumerate(tracks) if i not in used_t],
                [d for i, d in enumerate(dets) if i not in used_d])

    def update(self, detections: list, ts: float) -> list[Track]:
        for t in self._tracks:
            t.predict(ts)
        high = [d for d in detections if d.conf >= self.high_conf]
        low = [d for d in detections if d.conf < self.high_conf]

        matches, unmatched_tracks, unmatched_high = self._associate(self._tracks, high, MATCH_IOU)
        matches2, _, _ = self._associate(unmatched_tracks, low, LOW_MATCH_IOU)
        seen = []
        for t, d in matches + matches2:
            t.update(d, ts)
            seen.append(t)
        for d in unmatched_high:  # only confident detections start new tracks
            t = _State(d, ts, next(self._ids))
            self._tracks.append(t)
            seen.append(t)

        self._tracks = [t for t in self._tracks if ts - t.last_seen <= self.max_lost_s]
        return [Track(t.id, t.cls, t.bbox, t.conf) for t in sorted(seen, key=lambda s: s.id)
                if t.hits >= self.min_hits]
