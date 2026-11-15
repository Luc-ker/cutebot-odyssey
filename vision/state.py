"""Build the `vision.state` message (T44, contracts C1/C3).

    build_state(tracks, giants, frame_shape, ts) -> dict

Pure function: pixel-space tracks and giants from the robot's camera in, one `vision.state` payload out.
Positions and sizes are in **view units** (C1): the camera frame is `0 ≤ x ≤ 1` left to right and
`0 ≤ y ≤ 1` top to bottom. `GiantIds` gives giants stable "g<n>" ids across frames.

Objects from a segmentation model also get `outline`: their mask contour as [x, y] points in view units, used
by the eye page's local renderer to cover the real object. `client_ts`, when given, is the eye page's own
timestamp for the frame (`camera.frame.t`), so the eye page can tell how old this state is.
"""
from __future__ import annotations

import itertools
import math
from typing import Sequence


def _clamp01(v: float) -> float:
    return min(max(float(v), 0.0), 1.0)


def box_to_view(bbox: Sequence[float], frame_shape: Sequence[int]) -> tuple[list[float], list[float]]:
    """Centre and size of a pixel box in view units, both clamped to [0, 1]."""
    h, w = frame_shape[:2]
    x1, y1, x2, y2 = (float(v) for v in bbox[:4])
    x1, x2 = _clamp01(x1 / w), _clamp01(x2 / w)
    y1, y2 = _clamp01(y1 / h), _clamp01(y2 / h)
    return [(x1 + x2) / 2, (y1 + y2) / 2], [x2 - x1, y2 - y1]


def outline_to_view(points, frame_shape: Sequence[int]) -> list[list[float]]:
    """Pixel outline points -> view units, clamped to [0, 1] and rounded to 0.001."""
    h, w = frame_shape[:2]
    return [[round(_clamp01(float(x) / w), 3), round(_clamp01(float(y) / h), 3)] for x, y in points]


def build_state(tracks, giants: list[dict], frame_shape: Sequence[int], ts: float,
                client_ts: float | None = None) -> dict:
    objects = []
    for t in tracks:
        pos, size = box_to_view(t.bbox, frame_shape)
        obj = {"id": int(t.id), "cls": str(t.cls), "pos": pos, "size": size,
               "conf": round(_clamp01(t.conf), 3)}
        outline = (getattr(t, "extra", None) or {}).get("outline")
        if outline and len(outline) >= 3:
            obj["outline"] = outline_to_view(outline, frame_shape)
        objects.append(obj)

    out_giants = []
    for i, g in enumerate(giants):
        pos, size = box_to_view(g["bbox"], frame_shape)
        out_giants.append({"id": str(g.get("id") or f"g{i + 1}"), "kind": g["kind"], "pos": pos, "size": size,
                           "edge": g["edge"]})

    state = {"frame_ts": float(ts), "objects": objects, "giants": out_giants}
    if client_ts is not None:
        state["client_ts"] = float(client_ts)
    return state


class GiantIds:
    """Stable "g<n>" ids for giants: a giant keeps its id while it stays near where it was, on the same edge."""

    def __init__(self, max_jump_px: float = 200.0, max_missing_s: float = 0.5):
        self.max_jump_px = max_jump_px
        self.max_missing_s = max_missing_s
        self._next = itertools.count(1)
        self._known: dict[str, tuple[tuple[float, float], str, float]] = {}  # id -> (centre, edge, last_ts)

    def reset(self) -> None:
        self._known.clear()

    def assign(self, giants: list[dict], ts: float) -> list[dict]:
        self._known = {k: v for k, v in self._known.items() if ts - v[2] <= self.max_missing_s}
        used: set[str] = set()
        out = []
        for g in giants:
            b = g["bbox"]
            c = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
            best, best_d = None, self.max_jump_px
            for gid, (kc, kedge, _) in self._known.items():
                if gid in used or kedge != g["edge"]:
                    continue
                d = math.dist(c, kc)
                if d <= best_d:
                    best, best_d = gid, d
            gid = best or f"g{next(self._next)}"
            used.add(gid)
            self._known[gid] = (c, g["edge"], ts)
            out.append({**g, "id": gid})
        return out
