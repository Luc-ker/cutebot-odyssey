# Hardware print files (T101)

| File | What | Print |
|---|---|---|
| `robot_marker_4x4_50_id0.svg` | Robot marker: ArUco `DICT_4X4_50`, id 0, 66 mm black square. Top edge = robot front | A4, 100 % / actual size, matt |
| `table_corner_markers_4x4_50_ids1-4.svg` | Optional table-corner markers for auto-calibration: id 1 TL, 2 TR, 3 BR, 4 BL, 60 mm each | A4, 100 % |
| `photos/` | Photos of the finished build (add them yourself) | |

Both sheets have a 50 mm ruler. Measure it after printing to check the scale. The markers were generated
with OpenCV 4 (`cv2.aruco.generateImageMarker`), and the SVGs were checked by drawing them and detecting
them again with `cv2.aruco.ArucoDetector`.

Build instructions: `docs/build.md`.
