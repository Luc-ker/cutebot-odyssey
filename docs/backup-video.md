# Backup demo recording (T103)

A last-resort video of one full two-minute run (whitepaper §12), for when everything fails on the day.
**The video is not stored in git.** It lives on two laptops and a USB stick, and this page says where.

Recording the demo screens is our own deliberate recording, separate from the game itself (which records
nothing; see `docs/privacy.md`). Only record teammates, or people who have said yes.

## What to record (all at the same time)

| Source | How | Settings |
|---|---|---|
| **A. Eye screen** (`/eye/`, robot's-eye view) | screen recorder on the laptop showing it | 1080p, 30 fps, **system audio on** (narration and effects come from the sound page on this laptop) |
| **B. Overhead map** (`/map/`) | screen recorder on the machine showing it (or a second window on the same laptop) | 1080p, 30 fps, no audio |
| **C. The table** | a phone on a tripod or held steady, showing the table, the robot and the person driving | 1080p, 30 fps, its own mic (records the music too) |

Screen recorders: **OBS Studio** (free, Windows/macOS/Linux, recommended: one scene per screen); or Windows
**Snipping Tool → Record** / **Win + Alt + R** (Xbox Game Bar); macOS **Cmd + Shift + 5**.

## Step by step

**Before (15 min):**
1. Install OBS on the eye laptop. Add a *Display Capture* (or *Window Capture* of the eye browser window) and
   *Desktop Audio*. Settings → Output → Recording format **mp4** (or mkv + remux), quality "High".
2. Do the same for the map screen, or capture it as a second source in the same OBS (a second scene, recorded
   with a second OBS instance, or use the side-by-side layout below directly).
3. Easiest option: one OBS, one scene with **eye view large on the left and map small on the right**, plus
   desktop audio. Then you only need to sync the phone video.
4. Everything at full brightness, notifications off (Windows Focus / macOS Do Not Disturb), status page closed.
5. Charge the table phone, clear 2 GB of space, tripod placed so the whole table and the driver are in frame.
6. Run the demo once as a rehearsal.

**Recording (5 min):**
7. Start the screen recording(s), then the phone video.
8. **Sync clap:** stand in front of the table phone and clap once, loudly, while someone presses the gamepad
   **horn** button at the same time. The horn sound and the clap give one shared moment in every recording.
9. Run the full §12 script (two minutes): drive, show the castle, play a song (world change and narration),
   hand on the table (giant), drop the crisp packet (threat and recoil), song change. Say the lines out loud.
10. Stop the phone, then the screen recording(s). Record 2–3 takes and keep the best.

**Editing (30–60 min):** free editors: **DaVinci Resolve**, **Shotcut**, or **Clipchamp** (built into Windows).
11. Import all clips. Line them up on the sync clap/horn (the spike in the audio waveform).
12. Layout: eye view full screen, the map as a corner picture-in-picture, and cut to the table phone video for
    the "put your hand on the table" and "drop a crisp packet" moments. Or a 3-way split for the whole run.
13. Keep the eye laptop's audio (narration and effects) as the main track. Mix in the phone's audio quietly
    for the room and music.
14. Add a title card ("Genrator: every genre generates a world") and, if wanted, captions for the spoken lines.
15. Export **H.264 MP4, 1080p, 30 fps**, ~10–20 Mbit/s. File name: `genrator-demo-backup-YYYY-MM-DD.mp4`.

**Store (5 min):**
16. Copy the file to **two laptops** (not a cloud-only folder; it must play with wifi off) and a USB stick.
17. **Test offline:** turn wifi off on each laptop, double-click the file, and play it start to end with sound.
18. Fill in the table below.

## Where the file is

| | Value |
|---|---|
| File name | |
| Length | ___ min ___ s |
| Size | ___ MB |
| Laptop 1 (whose, folder path) | |
| Laptop 2 (whose, folder path) | |
| USB stick (who has it) | |
| Played offline on both laptops (date, who) | ☐ ☐ |
| Recorded on (date, which take) | |

## On the day: when to use it

If after **2 minutes** of trying, the robot, the Jetson or the network still won't work: say *"Let us show
you a run we recorded earlier"*, play the video full screen with sound, and talk over it with the §12 lines.
Keep the robot on the table so judges can still pick it up.
