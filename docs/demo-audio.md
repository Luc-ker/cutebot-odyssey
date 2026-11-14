# Demo audio: playlist, cable fallback, microphone settings (T102)

The music sets the world, so the audio input has to work in a loud hall. There are two inputs. **Mic**: the
judge's phone or humming, the default. **Cable**: the fallback in noisy rooms.

## 1. The playlist

`eval/playlist.json` has one track per §7.6 world. It stores titles and links only. **Audio files never go in git.**

| World | Genre | Track | Licence | Status |
|---|---|---|---|---|
| Open ocean | sea shanty | *Drunken Sailor* (traditional; we can also sing it) | public domain | suggested |
| Volcanic wasteland | heavy metal | pick from Pixabay Music | Pixabay Content License | to pick |
| Snowy night village | lullaby | Brahms, *Wiegenlied* Op. 49 No. 4 | public domain composition | suggested |
| Kingdom | medieval lute | *Greensleeves* (traditional) | public domain composition | suggested |
| Neon city | synthwave | pick from Pixabay Music | Pixabay Content License | to pick |
| Rainforest | jungle drums | pick from Pixabay Music | Pixabay Content License | to pick |
| Royal court | classical strings | Vivaldi, *Spring* (Allegro) | public domain composition | suggested |
| Space station | ambient electronica | pick from Pixabay Music | Pixabay Content License | to pick |

**Pick and confirm each track (one person, ~45 min):**

1. Open the link for each row. For "to pick" rows, listen to 3–4 candidates and choose the one that sounds
   most obviously like the genre in its **first 10 seconds**. Gemini only hears ~7 s.
2. On the track's own page, read the licence. Public-domain *compositions* can still have copyrighted
   *recordings*, so the recording page itself must say public domain, CC0, CC BY, or Pixabay licence.
   Write the exact title, performer, URL and licence into `eval/playlist.json`.
3. Download each track **to the demo phone** (not into the repo), in playlist order. Make an offline
   playlist "Genrator" in the phone's music app.
4. Set `"status": "chosen"` once it passes the tests in §4.
5. Note a start time if the first seconds are quiet (e.g. "start at 0:12"): put it in `title`.

## 2. Cable setup (noisy rooms)

You need **one** of:

- **USB audio interface / USB sound card with a line or mic input** (recommended, ~£10 USB sound card with a
  pink mic jack works), plus a **3.5 mm male-to-male stereo cable**, plus the phone's **USB-C (or Lightning)
  to 3.5 mm headphone adapter**.
- **The laptop's own input**, only if it has a separate line/mic jack. Most laptops have one combo headset
  jack (TRRS). A normal 3.5 mm cable plugged into it is often not detected as an input. That's why the USB
  sound card is recommended.

**Steps:**

1. Plug the headphone adapter into the phone and the cable into the adapter.
2. Plug the USB sound card into the laptop and the cable's other end into its **mic/line in** (pink).
3. List devices: `python scripts/list_audio_devices.py`. Find the USB card, e.g. `3  USB Audio Device`.
4. Tell Genrator: `GENRATOR_AUDIO_DEVICE=3` (PowerShell `$env:GENRATOR_AUDIO_DEVICE="3"`), or a unique part
   of the name: `GENRATOR_AUDIO_DEVICE=USB`.
5. **Set the level:** phone volume to 50 %, play the loudest track, and run the meter:
   `python -m server.audio.capture --device 3 --seconds 20`
   - Aim for peaks around **−12 to −6 dBFS**. Over −3 means clipping: turn the phone down.
   - Under −30 means too quiet: phone up, or raise the input level in Windows Sound settings → Input →
     device → Volume. Turn off "audio enhancements" / AGC there if you can.
   - With the music paused it should drop below about **−56 dBFS**, so the silence gate (T67) sees silence.
6. Start the demo with that device set: `python scripts/launch.py`.
7. A speaker for the audience can still play the phone's audio: use a headphone **splitter** on the phone
   (one side to the cable, one to the speaker).

To switch back to the microphone: unset `GENRATOR_AUDIO_DEVICE` (or set it to the mic's index) and restart the brain.

**Mic settings:** use the laptop's built-in mic or a USB mic pointed at where the judge holds their phone,
~30 cm away. Windows Sound settings → Input → volume ~80 %. Same meter check: music at arm's length should
peak around −20 to −10 dBFS.

## 3. Without the room: `--audio-file`

For testing without a mic: `python scripts/launch.py --audio-file path/to/song.wav` (WAV only; keep the file
outside the repo).

## 4. Tests to run in a noisy room, and results

Do this at the venue (or play crowd noise from a laptop at speaking volume). For each test, start from the
Kingdom world (status page → Kingdom), play for 20 s, and note: did a new world arrive, was it the right
kind, how long did it take (`python scripts/latency.py`, press Enter at the change).

| Test | Input | World arrived? | Matches genre? | Time | Notes |
|---|---|---|---|---|---|
| Playlist: ocean | mic, phone at 30 cm | | | | |
| Playlist: ocean | cable | | | | |
| Playlist: volcano | mic | | | | |
| Playlist: volcano | cable | | | | |
| Playlist: snow | mic | | | | |
| Playlist: snow | cable | | | | |
| Playlist: kingdom | mic | | | | |
| Playlist: kingdom | cable | | | | |
| Playlist: neon | mic | | | | |
| Playlist: neon | cable | | | | |
| Playlist: rainforest | mic | | | | |
| Playlist: rainforest | cable | | | | |
| Playlist: court | mic | | | | |
| Playlist: court | cable | | | | |
| Playlist: space | mic | | | | |
| Playlist: space | cable | | | | |
| Humming a lullaby | mic, 20 cm | | | | |
| Humming / singing a shanty | mic, 20 cm | | | | |
| A judge's phone (their own song), quiet room | mic | | | | |
| A judge's phone, noisy room | mic | | | | |

**What works (fill in):**
- Mic in the noisy room: ...
- Cable: ...
- Humming: ...
- Recommended setting for the demo: ...
