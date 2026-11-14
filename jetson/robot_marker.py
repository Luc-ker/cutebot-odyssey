"""Find the robot from above (T41, contract C8).

    find_robot(frame) -> {"px": [u, v], "heading": rad, "bbox": [x1, y1, x2, y2], "method": "aruco"|"dots"} | None

Primary: ArUco marker id `MARKER_ID` from `DICT_4X4_50`, printed and mounted with the marker's top edge toward
the robot's front (see docs/robot-marker.md). Heading is the direction from the marker's bottom edge to its top
edge, in pixel space with the C1 convention (0 = +u, clockwise positive because v points down).

Fallback: two coloured dots, green at the front and magenta at the back, found by HSV threshold.
Never raises: anything unexpected returns None.
"""
from __future__ import annotations

import logging
import math

import cv2
import numpy as np

log = logging.getLogger("robot_marker")

ARUCO_DICT = cv2.aruco.DICT_4X4_50
MARKER_ID = 7

# HSV ranges (OpenCV hue 0..180) for the fallback dots.
FRONT_HSV = ((40, 80, 70), (85, 255, 255))     # green
BACK_HSV = ((140, 80, 70), (170, 255, 255))    # magenta
MIN_DOT_AREA = 30
MAX_DOT_GAP_PX = 250

_detector = None


def _aruco_detect(gray: np.ndarray):
    global _detector
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    if hasattr(cv2.aruco, "ArucoDetector"):
        if _detector is None:
            params = cv2.aruco.DetectorParameters()
            params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
            _detector = cv2.aruco.ArucoDetector(dictionary, params)
        return _detector.detectMarkers(gray)
    return cv2.aruco.detectMarkers(gray, dictionary)  # OpenCV < 4.7


def _from_aruco(frame: np.ndarray, marker_id: int) -> dict | None:
    gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = _aruco_detect(gray)
    if ids is None:
        return None
    for c, i in zip(corners, ids.flatten()):
        if int(i) != marker_id:
            continue
        tl, tr, br, bl = c.reshape(4, 2).astype(np.float64)
        centre = (tl + tr + br + bl) / 4
        front = (tl + tr) / 2 - (bl + br) / 2
        heading = math.atan2(front[1], front[0])
        xs, ys = c.reshape(4, 2)[:, 0], c.reshape(4, 2)[:, 1]
        return {"px": [float(centre[0]), float(centre[1])], "heading": heading,
                "bbox": [float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())], "method": "aruco"}
    return None


def _largest_blob(hsv: np.ndarray, lo, hi):
    mask = cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    if cv2.contourArea(c) < MIN_DOT_AREA:
        return None
    m = cv2.moments(c)
    return np.array([m["m10"] / m["m00"], m["m01"] / m["m00"]]), cv2.boundingRect(c)


def _from_dots(frame: np.ndarray) -> dict | None:
    if frame.ndim != 3:
        return None
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    front = _largest_blob(hsv, *FRONT_HSV)
    back = _largest_blob(hsv, *BACK_HSV)
    if front is None or back is None:
        return None
    (pf, rf), (pb, rb) = front, back
    v = pf - pb
    if np.linalg.norm(v) > MAX_DOT_GAP_PX or np.linalg.norm(v) < 1:
        return None
    centre = (pf + pb) / 2
    x1 = min(rf[0], rb[0]); y1 = min(rf[1], rb[1])
    x2 = max(rf[0] + rf[2], rb[0] + rb[2]); y2 = max(rf[1] + rf[3], rb[1] + rb[3])
    return {"px": [float(centre[0]), float(centre[1])], "heading": math.atan2(v[1], v[0]),
            "bbox": [float(x1), float(y1), float(x2), float(y2)], "method": "dots"}


def find_robot(frame: np.ndarray, marker_id: int = MARKER_ID, use_dots: bool = True) -> dict | None:
    try:
        if frame is None or frame.size == 0:
            return None
        found = _from_aruco(frame, marker_id)
        if found is None and use_dots:
            found = _from_dots(frame)
        return found
    except cv2.error as exc:
        log.debug("find_robot failed: %s", exc)
        return None


def render_marker(size_px: int = 400, marker_id: int = MARKER_ID, border_px: int | None = None) -> np.ndarray:
    """The marker image with a white quiet zone, for printing (`python -m jetson.robot_marker out.png`)."""
    d = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    img = cv2.aruco.generateImageMarker(d, marker_id, size_px)
    b = border_px if border_px is not None else size_px // 6
    return cv2.copyMakeBorder(img, b, b, b, b, cv2.BORDER_CONSTANT, value=255)


if __name__ == "__main__":
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else "robot_marker.png"
    cv2.imwrite(out, render_marker())  # privacy-ok: a generated printable marker, not camera data
    print(f"wrote {out} (DICT_4X4_50 id {MARKER_ID})")
