# Devpost submission draft: Genrator

*Copy each section into the matching Devpost field. Items in [brackets] need filling in on the day.*

**Tagline:** Every genre generates a world.

**Built with:** micro:bit, MicroPython, ELECFREAKS Cutebot, NVIDIA Jetson Orin Nano, OpenCV, YOLO, Python,
asyncio, WebSockets, WebRTC, JavaScript, Gemini API, [video model name], Web Speech API.

**Prize tracks:** DurHack overall; Best use of Gemini (MLH); Marshall Wace "New Worlds".

---

## Inspiration

From five centimetres off the ground, an ordinary room is enormous. A chair leg is a tower, a charger cable is a
river, the shadow under the table is a cave. We wanted to make a game of that tiny point of view. DurHack's theme
was *Composition*, and the thing that changes how a room *feels* fastest is music. So we let the music
compose the world.

## What it does

You drive a palm-sized robot car around a real table with a handheld controller, watching a live feed from a
phone strapped to it. An AI video model redraws that feed as a fantasy world. **The music decides which world.**
Play a sea shanty and the table becomes an ocean. Heavy metal makes it a volcanic wasteland, a lullaby a snowy
night village.

- **Gemini listens and looks in one call.** Every few seconds, a short audio clip and an overhead photo of the
  table go to Gemini, which returns a structured world: setting, mood, weather, time of day, palette, a role
  for **every real object** on the table, a restyle prompt for the video model, and a line of narration.
- **Objects keep their roles.** A Jetson with an overhead camera detects and tracks every object, and the game
  remembers what each one is in each world. The chair is the castle every time you drive past it, and it's a
  tall ship again when the shanty comes back.
- **The table is the level editor.** Drop a crisp packet on the table and it lands in the world as something new.
  If that's a dragon, the robot recoils.
- **Giants.** Lean over the table and your hand descends into the world as a giant's.
- **Rhythm.** The robot's lights and the visuals pulse to the beat, computed locally with no network delay.
- **A living map** on a second screen shows the table as a fantasy map, every object drawn as its role.
- **A narrator** announces arrivals, dangers and new worlds.

One person plays the mouse exploring the world, another plays the giant reshaping it, and whoever holds the music
controls reality.

## How we built it

- **Robot and controller:** an ELECFREAKS Cutebot and joystick gamepad, both on micro:bits running MicroPython.
  The gamepad drives the robot directly over micro:bit radio, so driving never depends on wifi. The robot has a
  radio failsafe, an ultrasonic safety stop and line-sensor edge detection. A third micro:bit on USB bridges
  radio to the laptop for light effects, recoil and telemetry.
- **The hub:** a small Python asyncio WebSocket pub/sub server on the laptop. Every part of the system publishes
  and subscribes to typed topics (`vision.state`, `audio.beat`, `world.current`...). We wrote shared contracts
  first, so 110 tickets could be built in parallel against stubs.
- **Overhead vision (Jetson Orin Nano):** OpenCV + YOLO (TensorRT where available) detect objects, a tracker with
  short re-identification keeps IDs stable, an ArUco marker gives the robot's pose, and hands and people are
  detected as giant shapes entering from a table edge. Positions are mapped to table coordinates through a
  calibrated homography.
- **Audio:** a fast layer on the laptop (beat tracking, energy, brightness, a silence gate) drives the lights and
  pulses. A slow layer keeps short in-memory clips for Gemini and detects when the song has changed, using a
  music signature (tempo, energy, brightness, chroma).
- **Gemini world composer:** one multimodal call with the audio clip, the overhead image and the object list
  returns JSON validated against our world schema. A guard checks every role against our roles vocabulary.
  A scheduler only adopts a new world when the music has meaningfully changed, and recognises a returning song
  so the old world (with its roles) comes back.
- **Robot's-eye view:** the phone streams over WebRTC to the eye page, which sends it to [video model] with a
  prompt built from the current world and the objects in front of the robot. If restyling drops, the raw feed
  shows with a world-coloured tint and role labels.
- **Map, narration and sound:** canvas layers for terrain, objects, the robot, danger zones, giants and beat pulses;
  a priority narration queue spoken with the browser's speech synthesis; synthesised sound effects.
- **Ops:** a one-command launcher, a status and control page (health of every module, message rates, reset,
  fallback worlds, fake events) and a privacy test that fails the build if anything writes images or audio to
  disk or uses face detection.

## Challenges we ran into

- [Fill in from the day. Candidates:]
- **Latency budget across three loops:** keeping beat → lights under 100 ms while the world loop takes seconds,
  and making a world change feel like one deliberate moment (a timed transition) instead of a flicker.
- **Radio contention:** the gamepad, the robot and the bridge share one micro:bit radio channel. We benchmarked
  packet loss at different rates and capped light commands.
- **Object identity:** tracker IDs change when a hand covers an object; roles have to survive that.
- **Phone camera over HTTPS:** phone browsers only allow the camera on secure pages, so we had to run our own
  certificate authority on the laptop.
- **Getting Gemini to return valid, consistent worlds** from audio + image, and guarding against roles that don't
  exist.

## Accomplishments that we're proud of

- [Fill in.] A judge can play *their own* song and watch the table transform around the same objects.
- Driving and rhythm effects keep working with no internet at all; the game degrades gracefully.
- 110 independent tickets built against shared contracts, with acceptance tests for the whitepaper's promises.

## What we learned

- [Fill in.] Multimodal models are good at *interpreting* music into a setting, but you need a memory layer to
  keep the world consistent.
- Design the contracts first, and the integration day becomes wiring rather than rewriting.
- Real-time AI video needs a fallback that is still fun.

## What's next for Genrator

- Several robots in the same world, each with its own player.
- A fully on-device version, with restyling running locally on stronger edge hardware.
- Music composed back from the world, so the room and the soundtrack shape each other.
- Persistent worlds that remember a room across sessions.
- Classrooms and therapy settings, where play at a tiny scale helps children explore stories and spaces.

## Privacy and responsible use

No faces are recognised, identified or stored: hands and people are only shapes for giant mode, and the snapshot
sent to Gemini has people blurred. No video or audio is recorded. The only audio that leaves the laptop is a
~7-second in-memory clip per Gemini call. Narration is short, in-world and not presented as fact. An automated
test enforces the no-recording and no-face-detection rules. Details: `docs/privacy.md`.

## AI use disclosure

*(MLH rules require disclosing AI tools used to build the project. Edit this to be accurate for the whole team.)*

**AI inside the product:** Google Gemini ([model, e.g. gemini-2.5-flash]) composes worlds, object roles and
narration from audio + image. [Video model] restyles the robot's camera feed in real time. A YOLO object detector
runs on the Jetson.

**AI used to build it:**
- **Claude Code (Anthropic)** helped write code, tests and documentation from our ticket specifications,
  including the integration and ops component (launcher, brain wiring, status page, latency and privacy checks,
  runbooks). The team reviewed and tested the output and made the design decisions.
- [Other tools, e.g. GitHub Copilot, ChatGPT, Gemini, and what they were used for.]
- The design (whitepaper, tickets, contracts) is our own. [Say if AI helped draft any of it.]

---

## Submission checklist

- [ ] Every section above filled in, no [brackets] left
- [ ] Team members added on Devpost and in `README.md`
- [ ] Repo link, and the backup demo video uploaded (see `docs/backup-video.md`)
- [ ] 3–5 screenshots: eye view, map, the robot on the table, status page
- [ ] Prize tracks selected
