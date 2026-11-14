# Genrator — Whitepaper

*Working title. DurHack 2026, theme "Composition".*

> **Every genre generates a world.**

---

## 1. One-sentence summary

Genrator is a palm-sized robot that you drive around a real table while seeing through its eyes, and whatever music is playing decides which miniature world that table becomes: a sea shanty turns it into an ocean, heavy metal into a volcanic wasteland, a lullaby into a snowy night, with every real object the robot discovers given a remembered role in that world.

---

## 2. The idea in plain words

From five centimetres off the ground, an ordinary room is enormous. A chair leg is a tower, a laptop charger cable is a river, the shadow under the table is a cave. Genrator takes that tiny point of view and makes it a game.

A player drives a small robot car with a handheld controller. A phone mounted on the robot streams its view to a screen, and an AI model redraws that view live in the style of a fantasy world. Everything happens in first person: there is no view from above and no map. The same camera feed is used to recognise the objects the robot sees, and the system keeps a memory of what each object *is* in the current world. The chair is the castle, and it stays the castle every time you drive past it.

What sets the world is music. Anyone can play a song from their phone or hum a tune. Gemini listens to a few seconds of that audio while looking at what the robot sees, and composes a world to fit: its setting, mood, weather and time of day, a role for every object the robot has discovered, and a line of narration spoken aloud as the player arrives. Change the song and the same table becomes a different world.

A hand reaching down in front of the robot appears inside the world as a giant. Setting a new object down in front of the robot adds something new to the world. One person plays the mouse exploring the world, another plays the giant reshaping it, and whoever holds the music controls reality.

---

## 3. How it fits the theme

The DurHack 2026 theme is **Composition**. Genrator uses the word in three senses at once:

1. **Musical composition.** The music is the input that decides the world.
2. **Visual composition.** The arrangement of real objects on the table is the layout of the level.
3. **Composing systems.** A robot, a phone camera, an object-vision model, a multimodal language model, a real-time video model and an audio pipeline are composed into one experience.

---

## 4. The experience, step by step

1. The player picks up the controller. The screen shows the robot's-eye view of the table, already redrawn as a world.
2. As the robot drives, the objects it sees are given roles; the HUD names what is straight ahead ("Ahead: Stormkeep, a castle").
3. A song starts playing. Within a few seconds the world visibly pulses to the beat, and the robot's lights flash in time.
4. Gemini finishes listening. The world morphs into one that matches the music, a narrator voice announces where the player has arrived, and every object changes to its new role.
5. The player drives around. Objects keep their roles as they come in and out of view.
6. Someone reaches down in front of the robot. In the robot's view, a giant's hand descends from the sky into the world.
7. Someone sets a new object down in front of the robot. It is announced with a new role, and if that role is a threat (for example a dragon), the robot reacts when it drives up to it.
8. Someone changes the song. The world transforms again around the same physical table.

---

## 5. Hardware

| Component | Role in Genrator |
|---|---|
| **ELECFREAKS micro:bit Smart Cutebot** | The robot body. Two-wheel drive, onboard RGB lights, ultrasonic distance sensor and line sensors. Driven by a micro:bit. |
| **micro:bit (on the Cutebot)** | Receives drive commands by radio, drives motors, controls the robot's lights, reports ultrasonic distance. |
| **ELECFREAKS joystick gamepad** (with a micro:bit) | The handheld controller. Joystick for driving, coloured buttons for actions. Sends commands to the Cutebot by micro:bit radio. |
| **Bridge micro:bit** (plugged into the laptop by USB) | Lets the software send commands to the robot (light effects, recoil manoeuvres) and receive sensor readings, over the same radio channel. |
| **Phone mounted on the Cutebot** | The robot's eye and the only camera. Streams first-person video from its browser camera. Chosen because a USB webcam needs a host computer and the Cutebot is too small to carry one; the phone carries its own battery and wifi. |
| **Raspberry Pi Debug Probe** | Development and debugging of the boards. |
| **Rechargeable AA batteries** | Power for the Cutebot and the gamepad. |
| **Crocodile clip leads and jumper wires** | Prototyping connections. |
| **Laptop** | Hosts the hub and web pages, the vision service (object detection on the phone's frames), the audio pipeline, the music input and the calls to Gemini and the video model. |
| **Screen** (the laptop, or a monitor) | The robot's-eye view. A second screen can show the status page for the team. |
| **Speaker** | Narration and sound effects. |
| **Microphone** (laptop microphone or USB microphone) | Listens to the music that sets the world. |

---

## 6. System overview

```
             ┌──────────── Music (phone, speaker, humming) ────────────┐
             ▼                                                          │
   [Microphone] ──► Audio pipeline (laptop)                             │
                     ├─ Fast layer: beat, tempo, loudness, energy ──────┼──► world pulses, robot lights
                     └─ Slow layer: 5–10 s audio clip ──┐               │
                                                        ▼               │
   [Phone on Cutebot] ──WebRTC──► Eye page ──frames──► Vision (laptop) ──► World state ──► Gemini (audio + robot's view in,
                                     │                (objects in view,   (roles, IDs,       structured world out)
                                     │                 hands)              in view or not)    │
                                     │                                                        ├─► World definition + roles
                                     │                                                        ├─► Restyle prompt ──┐
                                     │                                                        └─► Narration ──► Text-to-speech ──► Speaker
                                     └──► Video model (restyled) ◄─────────────────────────────────────────────────┘
                                                   │
                                                   ▼
                                           Robot's-eye screen
   [Gamepad] ──radio──► [Cutebot]  ◄──radio── [Bridge micro:bit] ◄── game logic (lights, recoil)
```

Three loops run side by side:

- **Control loop** (milliseconds): gamepad to robot by radio. Never depends on the network.
- **Rhythm loop** (tens of milliseconds): the audio's beat and energy drive visual pulses and robot lights. Runs locally.
- **World loop** (seconds): Gemini re-reads the music and what the robot sees, and composes or updates the world.

---

## 7. Functionality in detail

### 7.1 Driving the robot

- The joystick drives the Cutebot: forward and back on one axis, turning on the other, with speed proportional to how far the stick is pushed.
- The gamepad sends commands to the Cutebot's micro:bit over micro:bit radio, so driving works even if wifi fails.
- Gamepad buttons are mapped to actions:
  - **Light:** flash the robot's headlights (in the world, a lantern or torch).
  - **Horn:** play a sound effect suited to the current world (a horn in a kingdom, a ship's bell at sea).
  - **Shout:** trigger narration of what is directly ahead.
  - **Reset:** recentre the world and replay the arrival narration.
- **Safety stop:** the robot reads its ultrasonic sensor and refuses to drive forward into an obstacle closer than a set distance, and the line sensors can be used to stop at the table edge (for example by marking the edge with tape).

### 7.2 The robot's-eye view

- A phone mounted on the Cutebot, at robot height, streams its camera feed from a browser page. It is the only camera in the system.
- The stream goes to a real-time video-to-video model that redraws each frame in the style of the current world, guided by a text prompt.
- The restyled feed is shown full-screen on the main display, with a small overlay showing:
  - the current world's name,
  - the role of the object the robot is facing, when known,
  - a beat indicator.
- The restyle prompt changes whenever the world changes, so the same camera feed is redrawn as an ocean, a wasteland or a snowy night.
- When the robot is close to a known object, that object's role is injected into the prompt so the model draws it consistently (for example "a stone castle tower in the foreground").

### 7.3 Seeing through the robot's eyes

- The eye page on the laptop receives the phone's stream. A few times a second it sends a small frame to the vision service on the laptop.
- The vision service runs an object detection model on every frame to find the objects in view: chairs, bottles, cups, bags, laptops, books, toys and so on.
- Each detected object gets a **persistent ID**. While it stays in view, a tracker follows it from frame to frame. When the robot turns away and later sees it again, the object is **recognised by its appearance** (its class and colours) and gets its old ID back.
- The vision service also finds **hands and people** reaching into the view from the top or the sides (used by Giant mode).
- Positions are in **view coordinates**: where in the frame an object is (left, centre, right) and how much of the frame it fills. Bigger means closer. The ultrasonic sensor adds the real distance to whatever is straight ahead.
- There is no map of the table and no position for the robot: everything is relative to what the robot sees.
- The output is a live **world state**: every object discovered so far with ID, class, where it was last seen in the view, whether it is in view now, when it was first and last seen, and its current role.

### 7.4 World memory

- When the robot sees an object for the first time, it is given a role in the current world, and that role is stored against its ID.
- The role stays with the object:
  - when the robot turns away and comes back to it,
  - when the object is briefly hidden by a hand.
- An object out of view is remembered for several minutes, so it is recognised and keeps its role when the robot looks at it again.
- When the world changes because the music changes, every object is given a new role in the new world, but the system remembers the mapping per world: switch back to the earlier song and the chair is the castle again.
- This memory is what separates Genrator from a plain video filter. A filter guesses again on every frame; Genrator knows what each thing is.

### 7.5 The room as level editor

- **Adding an object adds to the world.** An object set down in front of the robot is detected, given a role suited to the current world, announced by the narrator and drawn into the robot's view.
- **Exploring discovers the world.** Each object the robot sees for the first time is a new place or creature, announced as the robot finds it.
- **Clustering changes meaning.** Several objects together in view can be read as a single place (for example three cups become a village).
- **The free space matters too.** Open ground becomes open terrain (plains, open sea, desert), and the space under the table becomes a cave or the deep sea, depending on the world. These words go into the restyle prompt and the narration.

### 7.6 Music sets the world

The core mechanic. Any music near the microphone decides the world.

**Music sources:**

- a song played from a phone or laptop,
- a judge's own phone, held near the microphone,
- humming, singing or whistling,
- a fixed playlist of demo songs, played through a cable in noisy rooms.

**Two layers of listening:**

1. **Fast layer, on the laptop, continuous.**
   - Detects the beat and tempo.
   - Measures loudness and energy.
   - Estimates brightness of the sound (bright and airy versus dark and heavy).
   - Drives effects instantly, with no network involved (see 7.9).
2. **Slow layer, Gemini, periodic.**
   - Every five to ten seconds, captures a short clip of the audio.
   - Sends it to Gemini with the robot's current view (see 7.7).
   - If the music has meaningfully changed (a new song, or a big shift in mood), the world is recomposed. If not, the current world stays.

**Examples of music to world:**

| Music | World | The chair becomes | Under the table |
|---|---|---|---|
| Sea shanty | Open ocean | A tall ship | The deep sea |
| Heavy metal | Volcanic wasteland | A fortress | A lava cave |
| Lullaby | Snowy night village | A watchtower | A bear's den |
| Medieval lute | Kingdom | A castle | A dragon's cave |
| Synthwave | Neon city | A skyscraper | The subway |
| Jungle drums | Rainforest | A temple | A hidden ruin |
| Classical strings | Royal court | A palace | Catacombs |
| Ambient electronica | Space station | A docking tower | Engine room |

These are illustrations. Gemini composes the world from the actual audio, so unexpected music produces unexpected worlds.

### 7.7 Gemini as the world composer

The multimodal heart of the project. One Gemini call takes several kinds of input and returns several kinds of output.

**Input, in one call:**

- a short audio clip of the music,
- the robot's current view (people blurred),
- the list of objects the robot has discovered, with IDs, classes and whether each is in view,
- the current world, if any, so changes can be smooth.

**Output, as structured data in a fixed schema:**

```json
{
  "world": {
    "name": "The Drowned Kingdom",
    "setting": "stormy open ocean",
    "mood": "adventurous",
    "time_of_day": "dusk",
    "weather": "rain",
    "palette": ["deep teal", "storm grey", "lantern gold"]
  },
  "roles": [
    { "object_id": 3, "role": "ship", "name": "The Salt Queen", "behaviour": "neutral" },
    { "object_id": 7, "role": "lighthouse", "name": "Old Beacon", "behaviour": "friendly" },
    { "object_id": 9, "role": "sea_serpent", "name": "The Coil", "behaviour": "threat" }
  ],
  "terrain": { "open_space": "open sea", "under_table": "the deep" },
  "restyle_prompt": "first-person view at sea level in a stormy ocean at dusk, rain, wooden ships, lantern light, painterly",
  "narration": "The storm rolls in as you sail into the Drowned Kingdom. Keep clear of the Coil."
}
```

**What Gemini decides:**

1. The world the music implies: name, setting, mood, time of day, weather, colour palette.
2. A role for every object the robot has discovered that fits that world, with a name and a behaviour (friendly, neutral or threat).
3. What the empty space and the area under the table become.
4. The prompt for the video model that redraws the robot's view.
5. A line of narration welcoming the player into the world.

**Guards around Gemini, so the demo is reliable:**

- **Fixed role vocabulary.** Gemini must pick roles from a known list, each with an icon, a prompt phrase and a behaviour. Anything outside the list is rejected and replaced with a default.
- **Schema validation.** Responses that do not match the schema are discarded.
- **Hold the last world.** If a call fails, times out or returns rubbish, the current world simply stays.
- **Rate limiting.** Calls are spaced out, and a new world is only adopted when it clearly differs from the current one, so the world does not flicker.
- **Smooth transitions.** A world change is shown as a deliberate morph, not a cut (see 7.12).

**Why Gemini is load-bearing:** without it, nothing turns music into a world, nothing assigns roles, and no narration is written. Removing Gemini stops the demo.

### 7.8 Narration

- Each new world is announced aloud: a short line naming the world and setting the scene.
- New objects are announced when they appear ("A sea serpent rises from the deep.").
- Pressing the Shout button narrates what is directly ahead of the robot.
- Narration text comes from Gemini; it is spoken with text-to-speech in a voice suited to the world where possible.
- Narration is kept short and never overlaps itself.

### 7.9 Moving to the beat

The fast audio layer makes the world feel alive instantly, before Gemini has answered.

- The robot's-eye view pulses subtly on each beat (brightness, glow or vignette).
- The Cutebot's RGB lights flash in time with the beat, through the bridge micro:bit.
- Louder, more energetic music makes effects stronger; quiet music makes them calm.
- When the music stops, the world stays but falls still and quiet.

### 7.10 Giant mode

- When a hand reaches into the robot's view (from above or from the side), or a person is in view, the system marks a **giant** in the world.
- In the robot's view, the giant is drawn as a colossus suited to the world: a stone titan in a kingdom, a sea god at sea, a frost giant in the snow, with a sound effect and narration.
- Objects set down by a giant arrive "from the sky": they appear with a landing effect and are announced.
- Giant mode turns the demo into a two-player game: one person explores as the mouse, the other reshapes the world as the giant.

### 7.11 The world reacts

- Objects with a **threat** behaviour (a dragon, a sea serpent, a lava beast) are dangerous up close.
- When the robot drives up to a threat (it is ahead and fills a large part of the view, or the ultrasonic sensor says it is very close):
  - the robot's lights flash red,
  - a warning sound plays,
  - the robot performs a short automatic recoil (reverse and turn), overriding the joystick for a moment,
  - the narrator reacts.
- **Friendly** objects have a calm effect when approached: lights turn warm, a pleasant sound plays.
- The ultrasonic sensor makes real obstacles solid in the world: if the robot is physically blocked, the narrator describes the wall, cliff or reef in front of it.

### 7.12 World transitions

- When the music changes enough for a new world, the change is shown as an event:
  - the robot's view blends from the old world's style to the new,
  - each object takes its new role,
  - the restyle prompt blends from the old world to the new,
  - the robot's lights shift to the new world's colours,
  - the narrator announces the arrival.
- Returning to a song heard earlier restores that world and its remembered roles.

### 7.13 No map

- There is deliberately no overhead map. The game is first person: the player only knows the world through the robot's eyes, the HUD and the narrator.
- The status page shows the team what the system knows (services, message rates, the current world) for running the demo.

### 7.14 Talking objects (stretch)

- Driving up to an object lets it speak in character, using a short line from Gemini based on its role, name and behaviour.
- Objects remember the player within a session ("Back again, little one?").

### 7.15 Fallback and reliability

- **Driving never depends on the network**: it is radio from gamepad to robot.
- **Beat effects never depend on the network**: they are computed locally.
- **If the video model drops**, the robot's-eye screen shows the raw camera feed with a world-coloured overlay and the role labels, so the game still works.
- **If Gemini drops**, the current world holds; a small set of pre-composed worlds can be selected by button.
- **If the phone or the vision service stops**, objects drop out of view but keep their roles, and driving, beat effects and narration carry on.
- **Noisy room**: the music can be fed by cable instead of the microphone.
- **One-command reset** restores the demo to a clean starting state.
- **A recorded video** of a full run is kept locally as a last resort.

---

## 8. The roles vocabulary

Gemini must choose from a fixed list. Each role has an icon, a default behaviour, a sound, and a description for the video prompt. Example entries:

| Role | Behaviour | Typical worlds |
|---|---|---|
| castle, palace, fortress, temple, skyscraper | neutral | kingdom, royal court, wasteland, jungle, neon city |
| tower, watchtower, lighthouse, beacon | friendly | most worlds |
| village, market, harbour, camp | friendly | most worlds |
| ship, raft, boat | neutral | ocean |
| forest, grove, jungle patch | neutral | kingdom, jungle |
| mountain, volcano, cliff, glacier | neutral | wasteland, snow |
| river, bridge, road | neutral | most worlds |
| treasure, relic, crystal | friendly | most worlds |
| dragon, sea serpent, lava beast, yeti, robot sentinel | threat | world-dependent |
| giant | special | all worlds, assigned by the system, never by Gemini |

---

## 9. Data model

**Tracked object**

| Field | Meaning |
|---|---|
| `id` | Persistent ID from tracking |
| `class` | What the detector thinks it is (bottle, chair, cup) |
| `position` | Where it was last seen in the robot's view (view coordinates) |
| `size` | How much of the view it filled (bigger = closer) |
| `visible` | Whether it is in view now |
| `first_seen`, `last_seen` | Timestamps |
| `roles_by_world` | Map from world ID to assigned role, name and behaviour |

**World**

| Field | Meaning |
|---|---|
| `id` | Unique ID for this world |
| `name`, `setting`, `mood`, `time_of_day`, `weather`, `palette` | From Gemini |
| `terrain` | What open space and the under-table area become |
| `restyle_prompt` | Prompt for the video model |
| `music_signature` | Tempo and energy summary, used to recognise a returning song |

**Robot state**

| Field | Meaning |
|---|---|
| `facing` | The object straight ahead in the view, if any |
| `distance_ahead` | From the ultrasonic sensor |
| `light_colour` | Current light state |
| `override` | Whether a recoil manoeuvre is in control |

---

## 10. Responsiveness targets

| Interaction | Target |
|---|---|
| Joystick to robot movement | Immediate, under 100 ms |
| Beat to light flash and visual pulse | Under 100 ms |
| Robot camera to restyled frame on screen | Low enough to drive comfortably; measured in the first hour |
| Object seen to world state updated | Under half a second |
| New object to role assigned and announced | A few seconds |
| Song change to new world | Around five to fifteen seconds, shown as a deliberate transition |

---

## 11. Privacy and responsible use

- The robot's camera is used to detect hands and people only as shapes and colour regions for Giant mode. No faces are recognised, identified or stored, and people are blurred in every image sent to Gemini.
- No video or audio is recorded or kept beyond the short clips needed for each Gemini call.
- People can keep their hands out of the robot's view to stay out of the world.
- AI-generated narration is kept short and in-world, and is not presented as fact.
- Use of AI tools in building the project is disclosed, as the MLH rules require.

---

## 12. Demo script (two minutes)

| Time | Beat |
|---|---|
| 0:00–0:15 | "From five centimetres up, a table is a kingdom. And the music decides which kingdom." Hand the judge the controller. |
| 0:15–0:45 | The judge drives. The HUD names the chair as a castle; turn away and back, and it is still the castle. |
| 0:45–1:05 | Ask the judge to play any song from their phone. The world pulses, then transforms, and the narrator welcomes them. |
| 1:05–1:25 | "Reach down in front of the robot." A giant's hand lands in the world. Set a teddy bear down in front of it: a threat appears, and when the judge drives at it, the robot recoils. |
| 1:25–1:45 | "Gemini hears the music and sees through the robot's eyes in one call, and composes the world, every object's role and the narration. The vision model recognises every object the robot finds and remembers what it is." |
| 1:45–2:00 | What we learned, honest limits, and the line: "Every genre generates a world." |

---

## 13. Prize alignment

| Prize | How Genrator fits |
|---|---|
| **DurHack overall** (creativity, technical execution, research and learning, polish) | Theme fit through music composing the world, a physical robot, a judge who takes part directly. |
| **Gemini track** (judge focused on multimodal) | Audio and image in, structured world, prompts and narration out, in one call. Gemini is load-bearing. |
| **Marshall Wace "New Worlds"** | Each song opens a new world inside an ordinary room. |
| **Neptune North, QRT, SGX, Waterstons, RS** | Not targeted. RS requires an Arduino UNO Q, which the team does not have. |

---

## 14. Known limitations

- The restyled view depends on a cloud video model and a stable network.
- Real-time restyling can drift; the same object may look slightly different frame to frame, which is why roles are fixed by the world memory and injected into the prompt.
- Music recognition by Gemini is interpretive: two people may disagree on what world a song implies.
- A loud hall can confuse the microphone; cable input is the fallback.
- Vision only knows what the robot has seen. Objects the detection model has no name for (crisp packets, cables) are not detected, and two identical objects of the same class can swap roles after the robot turns away.
- There is no map: nothing knows where objects are on the table, only where they appear in the robot's view.
- One robot only; the system is built to support more.

---

## 15. Future directions

- Several robots in the same world, each with its own player.
- A fully on-device version, with restyling running locally on stronger edge hardware.
- Music composed back from the world, so the room and the soundtrack shape each other.
- Persistent worlds that remember a room across sessions.
- Use in classrooms and therapy settings, where play at a tiny scale helps children explore stories and spaces.
