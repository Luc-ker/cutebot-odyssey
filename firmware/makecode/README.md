# Drive the Cutebot from a phone over Bluetooth

With only one micro:bit (the one in the Cutebot), the phone talks to the robot directly over Bluetooth:

```
Android phone (Chrome, web/pad/) ──Bluetooth──► micro:bit in the Cutebot
```

MicroPython can't use Bluetooth on the micro:bit, so the robot runs a MakeCode program instead
(`cutebot_bluetooth.ts`, which replaces `firmware/cutebot/` on the robot).

**What works this way:** driving with an on-screen joystick, headlights, horn, and the ultrasonic stop (the
robot won't drive forward into something closer than 8 cm; the phone shows the distance).
**What doesn't:** the laptop can't reach the robot while the phone holds the Bluetooth link, so the game's
reactions on the robot itself (lights on the beat, recoil from threats) don't happen. The restyled view, worlds
and narration on the laptop are unaffected.

## 1. Put the program on the micro:bit (once)

1. Take the micro:bit out of the Cutebot (or leave it in, switched off) and plug it into the laptop with a
   **data** USB cable. A `MICROBIT` drive appears.
2. In Chrome, open **https://makecode.microbit.org** → **New Project** → name it `genrator-cutebot`.
3. At the top, switch from **Blocks** to **JavaScript**.
4. **Gear icon → Extensions** → search **bluetooth** → click it. If it asks to remove the **radio** extension,
   click **Remove extension(s) and add bluetooth**.
5. **Gear icon → Project Settings** → choose **No Pairing Required: Anyone can connect via Bluetooth** → **Save**.
   (Without this, the phone can't connect without a pairing ritual.)
6. Select everything in the editor, delete it, and paste the whole of `firmware/makecode/cutebot_bluetooth.ts`.
   There should be no red underlines.
7. **Download**. Either let MakeCode flash it straight to the connected micro:bit, or drag the downloaded
   `microbit-genrator-cutebot.hex` onto the `MICROBIT` drive. The yellow LED flickers while it copies.
8. The micro:bit's display shows a sleeping face: it's waiting for a phone.
9. Put the micro:bit back in the Cutebot (buttons and display facing up, the edge connector fully in) and
   switch the Cutebot on.

## 2. Open the controller page

Web Bluetooth only works on secure pages, and only in Chrome on Android or Chrome on a laptop. It doesn't work
in any iPhone browser (on an iPhone, the **Bluefy** app can open the page instead).

**Quickest test, on the laptop:** run `python3 -m server.hub` in the repo, then open
**http://localhost:8765/pad/** in Chrome. `localhost` counts as secure, so it works straight away. Use the arrow
keys or WASD to drive.

**On the Android phone**, pick one:

- **A. Let Chrome trust the laptop's address (fastest).** Start the hub on the laptop
  (`python3 -m server.hub`; the phone and laptop must be on the same wifi, a phone hotspot is safest). On the
  phone, open Chrome → `chrome://flags` → search **Insecure origins treated as secure** → enter
  `http://<laptop IP>:8765` (for example `http://10.249.38.167:8765`) → **Enabled** → **Relaunch**. Then open
  `http://<laptop IP>:8765/pad/`.
- **B. HTTPS from the hub.** Set up the certificate in `docs/network.md` §2 (also needed for the camera phone)
  and open `https://<laptop IP>:8765/pad/`.
- **C. Host the two files anywhere with HTTPS** (`web/pad/index.html` and `web/pad/pad.js`, for example on
  GitHub Pages). Then the phone doesn't need the laptop at all to drive.

## 3. Drive

1. Tap **Connect robot**, pick **BBC micro:bit [.....]** from the list, tap **Pair/Connect**.
2. The micro:bit shows a happy face and the page says **Connected**.
3. Drag the circle: up = forward, sideways = turn. Let go and the robot stops. **Lights** cycles headlight
   colours, **Flash** flashes red, **Horn** beeps (micro:bit V2 speaker), **Stop** stops.
4. If the page is closed, the phone locks, or Bluetooth drops, the robot stops by itself within 0.3 s.

## Troubleshooting

| Problem | Fix |
|---|---|
| "This browser can't use Bluetooth" | Use Chrome on Android or a laptop. Not an iPhone (except the Bluefy app). |
| "Bluetooth needs a secure page" | Use one of the options in step 2. |
| The micro:bit isn't in the list | It's off, out of range, still connected to another phone (only one at a time), or the program isn't on it. Press the micro:bit's reset button and try again. |
| Connects, then nothing moves | Cutebot switched off or batteries flat (the micro:bit can run from USB while the motors have no power). Check the face on the display changed to happy. |
| Turns the wrong way | Swap the sign of `turn` in `drive()` in `cutebot_bluetooth.ts` (left = t − turn, right = t + turn) and re-download. |
| Won't drive forward, page says "Too close" | Something is within 8 cm of the ultrasonic sensor. Change `STOP_CM` if it's too cautious. |
| MakeCode shows red underlines | The bluetooth extension isn't added (step 4), or only part of the file was pasted. |
