"""Click the four table corners to calibrate the overhead camera (T37).

    python -m jetson.calibrate_tool                 # live camera 0
    python -m jetson.calibrate_tool --file img.jpg  # a still image or clip
    python -m jetson.calibrate_tool --aruco         # auto: ArUco markers 0..3 taped at TL, TR, BR, BL

Click TL, TR, BR, BL (top-left as seen in the camera image). Keys: `u` undo, `r` restart, `s` save, `q` quit.
Saves `jetson/calibration.json`. Needs a display (run on the Jetson's desktop or with X forwarding).
In --aruco mode the corner of each marker that points at the table's corner is used.
"""
from __future__ import annotations

import argparse
import sys

import cv2
import numpy as np

from jetson.calibration import DEFAULT_PATH, Calibration

ORDER = ["TL", "TR", "BR", "BL"]
ARUCO_DICT = cv2.aruco.DICT_4X4_50 if hasattr(cv2, "aruco") else None


def grab_frame(args) -> np.ndarray:
    if args.file and args.file.lower().endswith((".jpg", ".jpeg", ".png")):
        img = cv2.imread(args.file)
        if img is None:
            sys.exit(f"cannot read {args.file}")
        return img
    from jetson.camera import Camera

    with Camera(index=args.index, file=args.file) as cam:
        for _ in range(10):  # let exposure settle
            _, frame = cam.read()
        return frame.copy()


def find_aruco_corners(frame: np.ndarray) -> list[list[float]] | None:
    """Marker ids 0..3 at TL, TR, BR, BL; use each marker's outer corner (the one nearest the image corner
    of the same name)."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    if hasattr(cv2.aruco, "ArucoDetector"):
        corners, ids, _ = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters()).detectMarkers(gray)
    else:  # OpenCV < 4.7
        corners, ids, _ = cv2.aruco.detectMarkers(gray, dictionary)
    if ids is None:
        return None
    found = {int(i): c.reshape(4, 2) for i, c in zip(ids.flatten(), corners)}
    if not all(k in found for k in range(4)):
        return None
    centre = np.mean([found[k].mean(axis=0) for k in range(4)], axis=0)
    # Outer corner = the marker corner furthest from the centre of all four markers.
    return [found[k][np.argmax(np.linalg.norm(found[k] - centre, axis=1))].tolist() for k in range(4)]


def click_corners(frame: np.ndarray) -> list[list[float]] | None:
    points: list[list[float]] = []
    win = "calibrate: click TL, TR, BR, BL  (u undo, r restart, s save, q quit)"

    def on_mouse(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
            points.append([float(x), float(y)])

    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(win, on_mouse)
    while True:
        view = frame.copy()
        for i, p in enumerate(points):
            cv2.circle(view, tuple(map(int, p)), 6, (0, 255, 255), -1)
            cv2.putText(view, ORDER[i], (int(p[0]) + 8, int(p[1]) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        if len(points) == 4:
            cv2.polylines(view, [np.int32(points).reshape(-1, 1, 2)], True, (0, 255, 0), 2)
        else:
            cv2.putText(view, f"click {ORDER[len(points)]}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
        cv2.imshow(win, view)
        key = cv2.waitKey(30) & 0xFF
        if key == ord("u") and points:
            points.pop()
        elif key == ord("r"):
            points.clear()
        elif key == ord("s") and len(points) == 4:
            cv2.destroyAllWindows()
            return points
        elif key in (ord("q"), 27):
            cv2.destroyAllWindows()
            return None


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--index", default=0)
    p.add_argument("--file")
    p.add_argument("--aruco", action="store_true")
    p.add_argument("--out", default=str(DEFAULT_PATH))
    args = p.parse_args()

    frame = grab_frame(args)
    corners = find_aruco_corners(frame) if args.aruco else click_corners(frame)
    if corners is None:
        sys.exit("calibration cancelled" if not args.aruco else "could not find ArUco markers 0-3")
    calib = Calibration(corners, (frame.shape[1], frame.shape[0]))
    calib.save(args.out)
    print(f"saved {args.out}: corners {np.round(corners, 1).tolist()}")


if __name__ == "__main__":
    main()
