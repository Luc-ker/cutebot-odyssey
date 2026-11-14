# Physical build: phone mount and edge tape (T101)

Everything here is hand work. Budget about an hour for two people. The phone on the robot is the only camera
(T111): there is no overhead camera, no rig and no marker to build. Fill in the **Record** boxes as you go and
add photos to `hardware/photos/` (phone photos, resized to ~1600 px).

The current build uses laptop compute and the phone camera. NVIDIA Jetson, Arduino, USB camera,
Raspberry Pi 5, debug probe and crocodile clips are removed from the build. The Cutebot uses its
onboard connectors. The two micro:bits already handle the robot and handheld controller independently;
leave their setup alone. No micro:bit needs to be connected to the laptop for phone video.

## Shopping and parts list

| Have | Item | For |
|---|---|---|
| ☐ | Existing handheld gamepad with its configured micro:bit | independent controller |
| ☐ | Cutebot with micro:bit, fresh rechargeable AA batteries + a second charged set | robot |
| ☐ | The robot phone + a short USB cable and power bank (charge between runs) | robot's eye |
| ☐ | Stiff corrugated cardboard (a delivery box), ~30 × 20 cm | mount |
| ☐ | 2–3 wide rubber bands or a 30 cm strip of elastic / Velcro straps | holding the phone |
| ☐ | Hot glue gun, or strong double-sided foam tape | fixing |
| ☐ | Craft knife, steel ruler, cutting mat | cutting |
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
   front of the phone if it looks at the ceiling. Everything the game knows comes from this view: objects
   must be in frame from about 10 cm to 1 m ahead, and a hand reaching down in front of the robot must come
   in from the top of the frame.
7. **Field of view.** If you know the phone camera's horizontal field of view, put it in `shared/config.json`
   as `CAMERA_HFOV_DEG` (default 65; most phone main cameras are 60–70° in landscape). It decides what counts
   as "straight ahead".
8. **Cable.** Leave a USB cable plugged into the phone while parked, so it charges between runs.

**Drive-straight test.** Put the robot on the table, push the joystick straight forward for 2 m. If it curves
more than ~20 cm to one side, the phone is off-centre: slide the cradle towards the side it curves *away*
from and retest. If it wheelies or the front scrapes, move the phone back or forward over the axle.

| Record | Value |
|---|---|
| Phone model, width × thickness | |
| Camera lens height above table | ___ cm |
| Robot + phone weight (optional) | ___ g |
| Drive-straight drift over 2 m | ___ cm |

## 2. Edge tape for the line sensors

The line sensors (T14) stop the robot from driving off the table when they see the tape.

1. Clean the table edge with a dry cloth.
2. **Choose tape:** matt **black** electrical tape on a light table (default `EDGE_VALUE = 1` in
   `firmware/cutebot/edge.py`). On a dark table use white tape and flip `EDGE_VALUE` to 0.
3. Stick a band **2–3 cm wide** (two strips side by side) all the way around the play area, **3–5 cm inside** the
   real edge, so the robot can stop in time. Press it flat; no wrinkles or gaps at the corners (overlap them).
4. **Test each sensor:** hold the robot by hand with its line sensors over the tape, then over bare table. On the
   Cutebot, the sensor LEDs underneath change (the laptop does not receive `robot.telemetry` in this independent build). If they read inverted, flip `EDGE_VALUE`.
5. **Drive test:** drive slowly towards the edge at 5 points around the table (each side and a corner). It must
   stop on the tape every time. Then try at full speed. If it overshoots, widen the band or move it further in.

| Record | Value |
|---|---|
| Tape colour / table colour | |
| Band width, distance in from edge | ___ cm, ___ cm |
| Stops at edge (slow, 5 tries) | ___ / 5 |
| Stops at edge (full speed, 5 tries) | ___ / 5 |

## 3. Acceptance run (T101)

1. Fresh batteries in the Cutebot. Phone at 100 %, unplugged, mounted, streaming `/phone/`.
2. Start a stopwatch. Drive around the whole table continuously for **15 minutes**, with stops and turns.
3. Every 5 minutes, check on the eye page: the view is level and not blocked by the elastic, objects ahead
   are named in the HUD, and note battery levels.

| Check | Result |
|---|---|
| Drove 15 min without the phone slipping or the robot stalling | ☐ yes |
| Phone battery start → end | ___ % → ___ % |
| Cutebot slowed down noticeably? (batteries) | |
| Eye page view clear and level at 0 / 5 / 10 / 15 min | ☐ ☐ ☐ ☐ |
| Date, who, photos in `hardware/photos/` | |

If the robot slows down within 15 minutes, swap to the second battery set before every demo run and note it
in the pre-demo checklist (`docs/network.md` §6).
