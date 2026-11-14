# Robot marker

The overhead camera finds the Cutebot by a printed **ArUco marker** on its top (`jetson/robot_marker.py`).

| | |
|---|---|
| Dictionary | `DICT_4X4_50` |
| Marker ID | `7` |
| Printed size | **5 cm × 5 cm** black square, plus a white border of at least 1 cm on every side |
| Orientation | The marker's **top edge points to the robot's front** (heading is measured bottom → top) |

## Printing

```bash
python -m jetson.robot_marker robot_marker.png   # 400 px marker + white quiet zone
```

Print at 100% scale (no "fit to page") so the black square is 5 cm. Measure it. Use matte paper:
glossy paper reflects the room lights and the marker disappears in the glare. Glue it to thin card so it stays flat.

Why 5 cm: with a 720p camera about 1 m above a 120 cm table, 5 cm is about 30 px across. Detection
needs roughly 15 px or more, so this leaves headroom for blur while the robot moves. If the camera is higher,
go up to 7 cm.

## Mounting

The phone stands upright on the front of the Cutebot. If the marker is directly under it, the camera can't see it.

```
        front (direction of travel)
   ┌───────────────────────┐
   │  [ phone, upright ]   │   ← phone mount at the very front
   │                       │
   │   ┌───────────────┐   │
   │   │   ▲ top edge  │   │   ← marker on a card on the rear half,
   │   │    ARUCO 7    │   │     top edge toward the front
   │   └───────────────┘   │
   └───────────────────────┘
        back
```

- Put the marker on the **rear half** of the robot, flat and level, on a card that sticks out a little past the
  rear wheels if needed.
- Nothing taller than the marker should sit behind it (the camera looks down, but cables can still cast shadows).
- Check from the camera: `python -m jetson.camera` together with the calibration tool view, or run
  `jetson/main.py` and check that `robot.seen` is true while you drive around all four corners.

## Fallback: two coloured dots

If the marker can't be printed or keeps being lost, stick two round dots of about 2 cm on the robot's top:
**green at the front, magenta at the back**, roughly 6 cm apart. `find_robot` falls back to them when no marker
is visible. They are less robust under coloured stage lighting, so prefer the marker.

## When the marker is lost

`jetson/robot_pose.py` (T42) keeps the last pose with `seen: false` instead of letting the robot jump.
Hands over the robot and the robot driving under the table edge are the usual causes.
