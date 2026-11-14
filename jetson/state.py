"""Build the `vision.state` message (T44, contracts C1/C3).

    build_state(tracks, robot_pose, giants, calib, ts, robot_bbox=None) -> dict

Pure function: pixel-space tracks, robot pose (already in table space, from T42) and giants in, one
`vision.state` payload out. Tracks overlapping the robot's bounding box are dropped, because the phone
standing on the robot must never become an object. `GiantIds` gives giants stable "g<n>" ids across frames.
"""
from __future__ import annotations

import itertools
import math
from typing import Sequence

import numpy as np

ROBOT_OVERLAP = 0.3   # fraction of a track's box covered by the robot box that excludes it


def _clamp01(v: float) -> float:
    return min(max(float(v), 0.0), 1.0)


def covered_fraction(box: Sequence[float], cover: Sequence[float]) -> float:
    """How much of `box` lies inside `cover` (0..1)."""
    ix = max(0.0, min(box[2], cover[2]) - max(box[0], cover[0]))
    iy = max(0.0, min(box[3], cover[3]) - max(box[1], cover[1]))
    area = max(1e-9, (box[2] - box[0]) * (box[3] - box[1]))
    return ix * iy / area


def overlaps_robot(bbox: Sequence[float], robot_bbox: Sequence[float] | None) -> bool:
    if robot_bbox is None:
        return False
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    centre_inside = robot_bbox[0] <= cx <= robot_bbox[2] and robot_bbox[1] <= cy <= robot_bbox[3]
    return centre_inside or covered_fraction(bbox, robot_bbox) >= ROBOT_OVERLAP


def box_to_table(bbox: Sequence[float], calib) -> tuple[list[float], list[float]]:
    """Centre and footprint size of a pixel box in table units, both clamped to [0, 1]."""
    x1, y1, x2, y2 = bbox
    corners = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float64)
    t = calib.to_table_many(corners, clamp=True)
    pos = calib.to_table([(x1 + x2) / 2, (y1 + y2) / 2])
    size = [_clamp01(t[:, 0].max() - t[:, 0].min()), _clamp01(t[:, 1].max() - t[:, 1].min())]
    return [_clamp01(pos[0]), _clamp01(pos[1])], size


def build_state(tracks, robot_pose: dict | None, giants: list[dict], calib, ts: float,
                robot_bbox: Sequence[float] | None = None) -> dict:
    objects = []
    for t in tracks:
        if overlaps_robot(t.bbox, robot_bbox):
            continue
        pos, size = box_to_table(t.bbox, calib)
        objects.append({"id": int(t.id), "cls": str(t.cls), "pos": pos, "size": size,
                        "conf": round(_clamp01(t.conf), 3)})

    robot = None
    if robot_pose and robot_pose.get("pos") is not None:
        heading = robot_pose.get("heading")
        heading = 0.0 if heading is None else float(heading)
        if heading <= -math.pi:
            heading += 2 * math.pi
        robot = {"pos": [_clamp01(robot_pose["pos"][0]), _clamp01(robot_pose["pos"][1])],
                 "heading": heading, "seen": bool(robot_pose.get("seen"))}

    out_giants = []
    for i, g in enumerate(giants):
        pos, size = box_to_table(g["bbox"], calib)
        out_giants.append({"id": str(g.get("id") or f"g{i + 1}"), "kind": g["kind"], "pos": pos, "size": size,
                           "edge": g["edge"]})

    return {"frame_ts": float(ts), "objects": objects, "robot": robot, "giants": out_giants}


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
