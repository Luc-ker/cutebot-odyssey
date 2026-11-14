"""Generic detector for objects the model has no name for (T110, contract C8, whitepaper §7.3, §7.5, §12).

    gen = GenericDetector(calib)                 # calib optional: without it the whole frame is the table
    gen.detect(frame, known) -> list[Detection]  # cls="object", pixel space; [] while still learning
    gen.reset()                                  # relearn the empty table (on system.reset)

The demo drops a crisp packet on the table to create a threat, and the model (T38) has no class for crisp
packets, cables or most toys. This finds them as "something new on the table":

1. **Background.** The first ``learn_frames`` frames (at start and after ``reset``) are the empty table; their
   per-pixel median is the background, so a hand passing during learning doesn't get baked in.
2. **Foreground.** Each frame is compared with the background in colour (largest channel difference), so a
   red packet on a brown table counts even where the brightness matches. Small specks are opened away.
3. **Blobs → objects.** A blob becomes ``Detection(cls="object")`` unless it
   - is too small or too large (larger than ``MAX_AREA_FRACTION`` of the table: lighting or a person),
   - touches or crosses the table edge (that is a hand or a person: a giant, T43),
   - overlaps a known detection (IoU > 0.3, or mostly inside its box) or the robot's box.
4. **Keeping the background honest.**
   - Where nothing is in front of it, the background follows slow lighting drift.
   - *Ghosts*: when something that was there during learning is taken away, its old spot differs from the
     background but now looks just like the table around it. Such a blob is absorbed into the background
     instead of being reported.
   - A sudden change over most of the table (lights switched) restarts learning rather than reporting
     dozens of objects.

The pipeline (``jetson/main.py``) calls ``detect(frame, dets)`` after the model and then drops anything
overlapping the robot marker; ``robot_bbox`` here is an extra guard for callers that have it.

Runs on any machine with OpenCV, so the overhead camera can be on a laptop instead of a Jetson. Measured at
about 1.7 ms per 1280x720 frame on an Apple-silicon laptop at the 640 px working width; expect a few times
that on a Jetson's ARM cores.

Optional upgrade, not used: an open-vocabulary detector (e.g. YOLO-World / OWL-ViT with prompts like "crisp
packet", "cable", "toy") would also *name* these objects, but costs tens of ms per frame on a Jetson Orin
Nano, which would pull the vision loop below VISION_HZ. Background subtraction keeps the loop fast and only
needs to say "something new is here"; Gemini (T76) gives it a role anyway.

Privacy (§11): only blob shapes and mean colours are used; nothing is cropped, stored or identified.
"""
from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

from jetson.detector import Detection

LEARN_FRAMES = 12            # empty-table frames whose median becomes the background
DIFF_THRESHOLD = 32          # per-channel colour difference that counts as foreground
MIN_AREA_FRACTION = 0.0015   # of the table area (~ a 3 cm square on a 120 x 80 cm table)
MAX_AREA_FRACTION = 0.20     # bigger than this is a lighting change or a person, not an object
RELEARN_FRACTION = 0.35      # foreground over this much of the table at once → relearn
EDGE_BAND_PX = 6             # a blob within this many px (working scale) of the table outline touches it
WORK_WIDTH = 640             # downscale for speed
BG_ADAPT = 0.02              # background follows slow drift where nothing is in front of it
GHOST_DIFF = 20              # blob colour this close to the surrounding table → a ghost, absorb it
RING_PX = 9                  # width of the ring of table around a blob used for the ghost test
KNOWN_IOU = 0.3              # overlap with a known detection that makes a blob "already known"
KNOWN_COVERED = 0.6          # ... or this much of the blob inside a known box


def _iou(a: Sequence[float], b: Sequence[float]) -> float:
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _covered(a: Sequence[float], by: Sequence[float]) -> float:
    """Fraction of box ``a`` that lies inside box ``by``."""
    ix1, iy1, ix2, iy2 = max(a[0], by[0]), max(a[1], by[1]), min(a[2], by[2]), min(a[3], by[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area = (a[2] - a[0]) * (a[3] - a[1])
    return inter / area if area > 0 else 0.0


class GenericDetector:
    def __init__(self, calib=None, learn_frames: int = LEARN_FRAMES, diff_threshold: int = DIFF_THRESHOLD):
        self.calib = calib
        self.learn_frames = learn_frames
        self.diff_threshold = diff_threshold
        self.background: np.ndarray | None = None
        self._learning: list[np.ndarray] = []
        self._masks_for: tuple | None = None

    # ------------------------------------------------------------------ background

    def reset(self) -> None:
        """Forget the background; the next ``learn_frames`` frames are learned again (table should be empty)."""
        self.background = None
        self._learning = []

    @property
    def ready(self) -> bool:
        return self.background is not None

    def _prep(self, frame: np.ndarray) -> tuple[np.ndarray, float]:
        scale = min(1.0, WORK_WIDTH / frame.shape[1])
        small = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else frame
        if small.ndim == 2:
            small = cv2.cvtColor(small, cv2.COLOR_GRAY2BGR)
        return cv2.GaussianBlur(small, (5, 5), 0), scale

    def learn(self, frame: np.ndarray) -> bool:
        """Add an empty-table frame. Returns True once the background (their median) is ready."""
        img, _ = self._prep(frame)
        if self._learning and self._learning[0].shape != img.shape:
            self._learning = []
        self._learning.append(img)
        if len(self._learning) >= self.learn_frames:
            self.background = np.median(np.stack(self._learning), axis=0).astype(np.float32)
            self._learning = []
        return self.ready

    # ------------------------------------------------------------------ helpers

    def _table_masks(self, shape: tuple[int, int], scale: float):
        key = (id(self.calib), shape, scale)
        if self._masks_for != key:
            h, w = shape
            if self.calib is None:
                poly = np.int32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
            else:
                poly = np.int32(np.round(np.asarray(self.calib.corners_px) * scale))
            table = np.zeros((h, w), np.uint8)
            cv2.fillConvexPoly(table, poly.reshape(-1, 1, 2), 255)
            band = np.zeros((h, w), np.uint8)
            cv2.polylines(band, [poly.reshape(-1, 1, 2)], True, 255, thickness=2 * EDGE_BAND_PX)
            self._table, self._band = table, band
            self._table_area = max(1, int(np.count_nonzero(table)))
            self._masks_for = key
        return self._table, self._band, self._table_area

    # ------------------------------------------------------------------ detection

    def detect(self, frame: np.ndarray, known: Sequence | None = None,
               robot_bbox: Sequence[float] | None = None) -> list[Detection]:
        """New, un-named objects on the table, as ``Detection(cls="object")`` in pixel space."""
        if not self.ready:
            self.learn(frame)
            return []
        img, scale = self._prep(frame)
        if img.shape != self.background.shape:  # camera resolution changed: start again
            self.reset()
            self.learn(frame)
            return []
        table, band, table_area = self._table_masks(img.shape[:2], scale)
        cur = img.astype(np.float32)

        # OpenCV rather than NumPy element-wise maths here: ~10x faster on a 640 px 3-channel frame
        c0, c1, c2 = cv2.split(cv2.absdiff(cur, self.background))
        diff = cv2.max(cv2.max(c0, c1), c2)  # largest per-channel colour difference
        _, fg = cv2.threshold(diff, self.diff_threshold, 255, cv2.THRESH_BINARY)
        fg = cv2.bitwise_and(fg.astype(np.uint8), table)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

        if cv2.countNonZero(fg) > RELEARN_FRACTION * table_area:  # the lights changed, not the table
            self.reset()
            self.learn(frame)
            return []

        # the background follows slow drift where nothing is in front of it
        cv2.accumulateWeighted(cur, self.background, BG_ADAPT, mask=cv2.bitwise_not(fg))

        known_boxes = [list(getattr(k, "bbox", k)) for k in (known or [])]
        n, labels, stats, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
        min_area, max_area = MIN_AREA_FRACTION * table_area, MAX_AREA_FRACTION * table_area
        ring_kernel = np.ones((2 * RING_PX + 1, 2 * RING_PX + 1), np.uint8)
        out: list[Detection] = []
        for i in range(1, n):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < min_area or area > max_area:
                continue
            x, y, w, h = (int(v) for v in stats[i, :4])
            blob = labels[y:y + h, x:x + w] == i
            if (band[y:y + h, x:x + w][blob] > 0).any():
                continue  # touches the table edge: a hand or a person (a giant), not an object

            # ghost test: does the blob now look like the table around it?
            pad = RING_PX + 1
            y0, y1, x0, x1 = max(0, y - pad), min(fg.shape[0], y + h + pad), max(0, x - pad), min(fg.shape[1], x + w + pad)
            full = np.zeros((y1 - y0, x1 - x0), np.uint8)
            full[y - y0:y - y0 + h, x - x0:x - x0 + w][blob] = 1
            ring = (cv2.dilate(full, ring_kernel) > 0) & (full == 0)
            ring &= (fg[y0:y1, x0:x1] == 0) & (table[y0:y1, x0:x1] > 0)
            patch = cur[y0:y1, x0:x1]
            if ring.any():
                inside_col = patch[full > 0].mean(axis=0)
                ring_col = patch[ring].mean(axis=0)
                if np.abs(inside_col - ring_col).max() < GHOST_DIFF:
                    sel = full > 0
                    self.background[y0:y1, x0:x1][sel] = patch[sel]  # absorb the ghost
                    continue

            bbox = [x / scale, y / scale, (x + w) / scale, (y + h) / scale]
            if any(_iou(bbox, kb) > KNOWN_IOU or _covered(bbox, kb) >= KNOWN_COVERED for kb in known_boxes):
                continue  # the model already knows this one
            if robot_bbox is not None and (_iou(bbox, robot_bbox) > KNOWN_IOU or _covered(bbox, robot_bbox) >= 0.5):
                continue  # the robot itself
            strength = float(diff[y:y + h, x:x + w][blob].mean())
            out.append(Detection(bbox=[float(v) for v in bbox], cls="object",
                                 conf=float(np.clip(strength / 80.0, 0.3, 0.95)),
                                 extra={"source": "generic", "area_px": float(area / (scale * scale))}))
        return out
