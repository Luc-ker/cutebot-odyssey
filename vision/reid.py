"""Re-identification by appearance (T40, contract C8).

The camera rides on the robot, so every object leaves the view whenever the robot turns away, and the
tracker (T39) gives it a fresh ID when it comes back. ReId maps that fresh ID back to the old one, so the
chair is still the castle when the robot drives past it again.

    reid = ReId(config)
    tracks = reid.apply(tracker.update(dets, ts), ts, frame)   # frame is optional (colour histograms)

Position is no help once the robot has turned, so matching is by **appearance**: every object keeps a
running HSV colour histogram while it is in view. When it leaves the view it goes to a gallery and is
remembered for `OBJECT_FORGET_S`. A new track takes a remembered ID when

- the detector classes are compatible, and
- its colours are similar enough (histogram correlation ≥ `MIN_HIST_SIMILARITY`), or, for an object lost
  only a moment ago near the same spot in the frame, ≥ `NEAR_HIST_SIMILARITY`.

Among several candidates the most similar wins. An ID that is visible right now is never handed out
twice. The tracker can also swap IDs while the object never leaves the view (a missed frame, a jump in
its box): the old ID was in view last frame, so it is offered to the new track at once instead of
waiting a frame for the gallery, and the object keeps its ID (and so its role). Two look-alike objects of the same class (two identical red cups) can swap IDs; that is the price
of not knowing where the robot is.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

import cv2
import numpy as np

from vision.tracker import Track

DEFAULT_FORGET_S = 600.0
MIN_HIST_SIMILARITY = 0.6    # histogram correlation, -1..1
NEAR_HIST_SIMILARITY = 0.3   # looser bar for a short gap at the same place in the frame
SHORT_GAP_S = 1.5
NEAR_DIST = 0.15             # view units
HIST_BLEND = 0.2             # weight of the newest frame in the running histogram
MAX_GALLERY = 64
MAP_KEEP_S = 10.0            # tracker-id mappings unused for this long are dropped

# Detector classes that are easily confused with one another.
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


def similarity(a: np.ndarray | None, b: np.ndarray | None) -> float | None:
    if a is None or b is None:
        return None
    return float(cv2.compareHist(a.astype(np.float32), b.astype(np.float32), cv2.HISTCMP_CORREL))


@dataclass
class _Memory:
    out_id: int
    cls: str
    pos: tuple[float, float]       # view units, where it was last seen in the frame
    hist: np.ndarray | None        # running colour histogram
    last_seen: float


class ReId:
    def __init__(self, config: dict | None = None, forget_s: float | None = None):
        config = config or {}
        self.forget_s = forget_s if forget_s is not None else float(config.get("OBJECT_FORGET_S", DEFAULT_FORGET_S))
        self._map: dict[int, int] = {}          # tracker id -> output id
        self._map_seen: dict[int, float] = {}
        self._active: dict[int, _Memory] = {}   # output id -> appearance while in view
        self._lost: dict[int, _Memory] = {}     # output id -> appearance while out of view

    def reset(self) -> None:
        self._map.clear()
        self._map_seen.clear()
        self._active.clear()
        self._lost.clear()

    @property
    def remembered(self) -> int:
        """How many out-of-view objects are in the gallery."""
        return len(self._lost)

    def _match(self, cls: str, pos, hist, ts: float, taken: set[int]) -> int | None:
        best, best_s = None, -math.inf
        # In view last frame but not claimed this frame (its tracker id vanished) counts as just lost.
        candidates = {**self._active, **self._lost}
        for out_id, m in candidates.items():
            if out_id in taken or not compatible(cls, m.cls):
                continue
            s = similarity(hist, m.hist)
            recent_near = ts - m.last_seen <= SHORT_GAP_S and math.dist(pos, m.pos) <= NEAR_DIST
            if s is None:
                # No colours to compare: only a same-class object back at the same spot a moment later.
                if not (recent_near and cls == m.cls):
                    continue
                s = NEAR_HIST_SIMILARITY
            elif s < (NEAR_HIST_SIMILARITY if recent_near else MIN_HIST_SIMILARITY):
                continue
            if s > best_s:
                best, best_s = out_id, s
        return best

    def apply(self, tracks: list[Track], ts: float, frame: np.ndarray | None = None) -> list[Track]:
        self._lost = {k: m for k, m in self._lost.items() if ts - m.last_seen <= self.forget_s}
        h, w = frame.shape[:2] if frame is not None else (1, 1)

        out: list[Track] = []
        visible: dict[int, _Memory] = {}
        # Tracks that already have an output id first, so a new track can't take an id that is in view.
        ordered = sorted(tracks, key=lambda t: t.id not in self._map)
        for t in ordered:
            pos = ((t.bbox[0] + t.bbox[2]) / 2 / w, (t.bbox[1] + t.bbox[3]) / 2 / h) if frame is not None else (0.5, 0.5)
            hist = colour_hist(frame, t.bbox)
            out_id = self._map.get(t.id)
            if out_id is None or out_id in visible:
                out_id = self._match(t.cls, pos, hist, ts, set(visible))
                if out_id is None:
                    out_id = t.id
                self._map[t.id] = out_id
            self._map_seen[t.id] = ts
            prev = self._active.get(out_id) or self._lost.pop(out_id, None)
            if prev is not None and prev.hist is not None:
                if hist is None:
                    hist = prev.hist
                else:
                    hist = cv2.normalize((1 - HIST_BLEND) * prev.hist + HIST_BLEND * hist, None).flatten()
            visible[out_id] = _Memory(out_id, t.cls, pos, hist, ts)
            out.append(dataclasses.replace(t, id=out_id))

        # IDs in view last frame but not now go to the gallery.
        for out_id, m in self._active.items():
            if out_id not in visible:
                self._lost[out_id] = m
        self._active = visible
        if len(self._lost) > MAX_GALLERY:
            for out_id in sorted(self._lost, key=lambda k: self._lost[k].last_seen)[:len(self._lost) - MAX_GALLERY]:
                del self._lost[out_id]

        stale = [k for k, seen in self._map_seen.items() if ts - seen > MAP_KEEP_S]
        for k in stale:
            self._map.pop(k, None)
            self._map_seen.pop(k, None)
        # Keep the input order for callers.
        order = {id(t): i for i, t in enumerate(tracks)}
        pairs = sorted(zip(ordered, out), key=lambda p: order[id(p[0])])
        return [o for _, o in pairs]
