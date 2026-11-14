# Physical build: phone mount, marker, camera rig, edge tape (T101)

Everything here is hand work. Budget about 2 hours for two people. Fill in the **Record** boxes as you go and
add photos to `hardware/photos/` (phone photos, resized to ~1600 px).

## Shopping and parts list

| Have | Item | For |
|---|---|---|
| ☐ | Cutebot with micro:bit, fresh rechargeable AA batteries + a second charged set | robot |
| ☐ | The robot phone + a short USB cable and power bank (charge between runs) | robot's eye |
| ☐ | Stiff corrugated cardboard (a delivery box), ~30 × 20 cm | mount, marker card |
| ☐ | 2–3 wide rubber bands or a 30 cm strip of elastic / Velcro straps | holding the phone |
| ☐ | Hot glue gun, or strong double-sided foam tape | fixing |
| ☐ | Craft knife, steel ruler, cutting mat | cutting |
| ☐ | Printed `hardware/robot_marker_4x4_50_id0.svg` (and the corner-marker sheet) | marker |
| ☐ | Clear packing tape or a laminating pouch | protect the marker from glare and scuffs |
| ☐ | Tripod with a horizontal arm, **or** a clamp + broom handle / 1.5 m pole + gaffer tape | camera rig |
| ☐ | USB extension cable (2–3 m), active if the run is long | camera to Jetson |
| ☐ | Matt black electrical tape (PVC, 19 mm), 1 roll; white tape if the table is dark | edge tape |
| ☐ | Tape measure, kitchen scale (optional), phone with a stopwatch | measurements |

## 1. Phone mount on the Cutebot

The phone stands upright at the front of the robot, rear camera facing forward, as low as it can go.

1. **Check what must stay clear.** Look at the Cutebot from the front: the **ultrasonic sensor** (the two
   "eyes") must not be covered, and the **line sensors** underneath must stay clear. The micro:bit's
   power switch and USB port should still be reachable.
2. **Measure.** Record the phone's width, thickness and where its rear camera lens is
   (distance from the top edge and from the left edge, with the screen facing you).
3. **Cut the cradle.** From cardboard, cut:
   - a **base plate** as wide as the Cutebot and 4 cm deep,
   - a **back plate** as wide as the phone and 6 cm tall,
   - two **side triangles** (right angle, 4 cm × 6 cm) as braces.
   Glue the back plate upright onto the base plate's rear edge and the triangles behind it. You now have
   an "L" the phone leans against.
4. **Place it.** Stand the phone in the L **landscape** (long side horizontal), rear camera facing forward.
   Put the whole cradle on the robot so that:
   - the camera lens sits **above** the ultrasonic sensor and does not see it (check the camera app: no
     sensor in the bottom of the frame; if there is, move the phone up 5 mm with a cardboard shim),
   - the phone's weight is **over or just in front of the wheel axle**, not hanging off the front.
5. **Fix it.** Stick the base plate to the Cutebot's top with double-sided foam tape (removable). Loop 2
   rubber bands / elastic around the phone and the back plate, at both ends, clear of the camera lens.
6. **Tilt.** The camera should look straight ahead, or 5–10° down. Wedge a strip of cardboard under the
   front of the phone if it looks at the ceiling.
7. **Cable.** Leave a USB cable plugged into the phone while parked, so it charges between runs.

**Drive-straight test.** Put the robot on the table, push the joystick straight forward for 2 m. If it curves
more than ~20 cm to one side, the phone is off-centre: slide the cradle towards the side it curves *away*
from and retest. If it wheelies or the front scrapes, move the phone back or forward over the axle.

| Record | Value |
|---|---|
| Phone model, width × thickness | |
| Camera lens height above table | ___ cm |
| Robot + phone weight (optional) | ___ g |
| Drive-straight drift over 2 m | ___ cm |

## 2. Robot marker on top

The overhead camera finds the robot by this marker (T41: ArUco `DICT_4X4_50`, id 0). The marker's
**top edge points to the robot's front**.

1. **Print** `hardware/robot_marker_4x4_50_id0.svg`: open it in a browser → Print → Scale **100% / Actual
   size**, plain white paper, black-and-white. Measure the 50 mm ruler on the sheet with a ruler; if it's not
   50 mm, fix the print scale and reprint.
2. **Protect it:** cover it with clear packing tape, laminate it, or put it under a matt sticker sheet. **Matt is
   important.** A shiny marker reflects the ceiling lights and the camera can't read it.
3. **Mount a card:** cut a cardboard square 2 mm larger than the dashed line. Glue the marker on it, flat, no
   bubbles.
4. **Place it:** the marker goes **behind the phone**, flat and horizontal, as high as it can go without
   being hidden by the phone when seen from above. Raise it on two cardboard pillars (about 2 cm tall) so
   it sits above the micro:bit, clear of the phone's top edge. Arrow/top edge towards the robot front.
5. If the full 66 mm marker doesn't fit behind the phone, reprint at **75 %** (50 mm black square) and write
   the size below.
6. **Check from above:** stand over the table at camera height and take a phone photo looking straight down.
   The whole marker must be visible, not covered by the phone or the elastic.

| Record | Value |
|---|---|
| Printed marker size (black square) | ___ mm |
| Marker height above table | ___ cm |
| Distance marker centre → robot centre (forward/back) | ___ cm |

## 3. Overhead camera rig

The Arduino USB camera looks straight down and must see **all four table corners** with a little margin.

1. **Measure the play area** (the part of the table the robot drives on). Write it in
   `shared/config.json` as `TABLE_W_CM` (long side, the camera's x axis) and `TABLE_H_CM`. Defaults are 120 × 80.
2. **Height:** start with the camera **about 1.1–1.3 m above the table top** for a 120 × 80 cm area (higher for
   a bigger table). A wide-angle webcam needs less height.
3. **Build the rig**, one of:
   - **Tripod:** extend it fully next to the long side of the table, tilt the head so the camera faces straight
     down, and hang the camera over the middle of the table with a horizontal arm or a taped-on pole.
   - **Clamp and pole:** clamp a broom handle / pole to the back of a chair or the table leg, standing
     upright, with a second short piece at the top reaching out over the table centre. Gaffer-tape the camera
     to the end, lens down.
   Weight the base (a bag on the tripod legs) so a bump doesn't move it. **If the camera moves, you must
   recalibrate.**
4. **Point it:** the camera's long side (16:9) along the table's long side. Plug it into the Jetson with the USB
   extension and route the cable up the pole with tape so nobody snags it.
5. **Check the view:** on the Jetson, open the camera (the T36/T37 tools, or `cheese` / `guvcview`) and check:
   - all four corners visible, ~5 cm margin around the play area,
   - camera centred over the middle, image not tilted (table edges look straight and parallel),
   - no strong glare spot on the table from a ceiling light. If there is one, move the rig a little or turn
     that light off.
6. **Corner markers (optional, for T37 auto-calibration):** print `hardware/table_corner_markers_4x4_50_ids1-4.svg`
   at 100 %, cut out the four markers and tape them **just inside** the corners: id 1 top-left, id 2
   top-right, id 3 bottom-right, id 4 bottom-left (top/left as the camera sees it).
7. **Calibrate** with the T37 tool (`python3 jetson/calibrate_tool.py`): click the corners TL, TR, BR, BL.

| Record | Value |
|---|---|
| Play area | ___ × ___ cm |
| Camera height above table top | ___ cm |
| Rig type and where it stands | |
| Resolution used | ___ × ___ |
| Marker size in the image (pixels across, from a screenshot) | ___ px (want ≥ 40) |

## 4. Edge tape for the line sensors

The line sensors (T14) stop the robot from driving off the table when they see the tape.

1. Clean the table edge with a dry cloth.
2. **Choose tape:** matt **black** electrical tape on a light table (default `EDGE_VALUE = 1` in
   `firmware/cutebot/edge.py`). On a dark table use white tape and flip `EDGE_VALUE` to 0.
3. Stick a band **2–3 cm wide** (two strips side by side) all the way around the play area, **3–5 cm inside** the
   real edge, so the robot can stop in time. Press it flat; no wrinkles or gaps at the corners (overlap them).
4. **Test each sensor:** hold the robot by hand with its line sensors over the tape, then over bare table. On the
   Cutebot, the sensor LEDs underneath change (or check `robot.telemetry` `line` on the status page: `[1, 1]`
   over tape). If they read inverted, flip `EDGE_VALUE`.
5. **Drive test:** drive slowly towards the edge at 5 points around the table (each side and a corner). It must
   stop on the tape every time. Then try at full speed. If it overshoots, widen the band or move it further in.

| Record | Value |
|---|---|
| Tape colour / table colour | |
| Band width, distance in from edge | ___ cm, ___ cm |
| Stops at edge (slow, 5 tries) | ___ / 5 |
| Stops at edge (full speed, 5 tries) | ___ / 5 |

## 5. Acceptance run (T101)

1. Fresh batteries in the Cutebot. Phone at 100 %, unplugged, mounted, streaming `/phone/`.
2. Start a stopwatch. Drive around the whole table continuously for **15 minutes**, with stops and turns.
3. Every 5 minutes, check on the Jetson camera view: **all four corners and the marker visible**, and note
   battery levels.

| Check | Result |
|---|---|
| Drove 15 min without the phone slipping or the robot stalling | ☐ yes |
| Phone battery start → end | ___ % → ___ % |
| Cutebot slowed down noticeably? (batteries) | |
| Overhead camera sees 4 corners + marker at 0 / 5 / 10 / 15 min | ☐ ☐ ☐ ☐ |
| Date, who, photos in `hardware/photos/` | |

If the robot slows down within 15 minutes, swap to the second battery set before every demo run and note it
in the pre-demo checklist (`docs/network.md` §6).
