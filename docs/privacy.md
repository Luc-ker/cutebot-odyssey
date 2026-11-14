# Privacy in Genrator

*A plain-language summary of whitepaper §11, for judges and anyone at the table.*

**We don't know who you are, and we don't keep what we see or hear.**

## What the camera does

There is one camera: **the phone on the robot**, looking ahead at table height.

- It streams live video to the laptop's screen through the AI video model. Nothing is recorded.
- A few times a second the laptop looks at a small copy of the frame to find objects, and hands or people
  reaching into the robot's view. Hands and people are seen only as **shapes and colour regions** so they
  can appear as giants in the game. **No face is detected, recognised, identified or stored.** We use a
  general object detector (YOLO), with no face model. These frames only exist in memory, for a moment.
- **The snapshot** sent to Gemini (so it can see what the robot sees) has people **blurred** before it leaves
  the vision service, and it is never saved.

## What the microphone does

- The laptop listens continuously only to work out the **beat, loudness and brightness** of the music.
  These numbers are computed in memory and thrown away.
- Every few seconds, a **short clip (about 7 seconds)** is sent to Gemini so it can choose a world. The clip
  is built in memory, sent, and dropped. It is never written to disk.

## What is kept

- Only game state: which object has which role in which world (for example "object 3 is the castle"), and a
  small colour histogram per object so it can be recognised when the robot sees it again. These stay in
  memory while you play and are cleared with the reset button.
- Logs record events and timings. They never contain audio, images or video (the logger replaces any such
  data with its size, e.g. `<112000 bytes>`).

## Your choices

- Keep your hands out of the robot's view and you stay out of the world: the giant disappears.
- The narration is short, AI-generated and in-world. It is a story, not a statement of fact.

## How we check this

`tests/test_privacy.py` runs with the rest of our test suite. It reads all of our source code and **fails**
if anything:

- writes an image, video or audio file to disk (`cv2.imwrite`, `VideoWriter`, `soundfile.write`, writing
  a `.wav` with `wave`, saving an image, opening a `.jpg`/`.wav`/`.mp4`... for writing, or recording in the
  browser with `MediaRecorder`), or
- uses a face detection or recognition library or model (`face_recognition`, `dlib`, `deepface`,
  Haar face cascades, MediaPipe face detection, and similar).

The test includes a deliberately planted `cv2.imwrite` to prove it catches one. Writing to memory buffers
(as the Gemini clip does) is allowed. Any exception has to be marked in the code with a visible
`# privacy-ok:` comment, so it shows up in review.

## Third-party services

The audio clip and the blurred robot's-view snapshot go to **Google Gemini**; the robot's camera stream goes to the
**AI video model** for restyling. Both are processed under those providers' API terms. We do not ask them
to store anything.
