# Latency against the whitepaper §10 targets

Tool: `scripts/latency.py` (T98). It listens to the hub and prints p50/p95/max per path.
Times are taken when the script receives each message, so every path includes the same hub hop and no
clocks need to agree.

## How to measure

```bash
python scripts/launch.py --audio-file two_songs.wav     # or the live mic with real songs
python scripts/latency.py --seconds 120                  # in a second terminal
```

- **Beat → lights**: just let music play. Each `audio.beat` is paired with the next `robot.cmd {kind: "lights"}` within 250 ms.
- **Object → map**: move an object on the table every few seconds (or run `--replay object_moved`). A move is
  a `vision.state` position change of more than 0.01; it counts once `world.objects` shows the object within
  0.02 of the new position. Moves not shown within 3 s count as *missed*.
- **Song → world** and **song → transition**: press **Enter** in the latency terminal at the moment the song
  changes. The clock stops at the next `world.current` with a new world id and at the next `world.transition`.
  Do this at least 5 times.
- `python scripts/latency.py --selftest` checks the maths on synthetic messages without a hub.

### Joystick → movement (does not touch the laptop)

The gamepad talks to the Cutebot by radio, so the hub never sees it. Measure it with a slow-motion video:

1. Set a phone to slow-motion video (240 fps if it has it; 120 fps is fine).
2. Put the gamepad and the robot next to each other on the table, both in frame, the robot's wheels visible.
3. Start recording. Push the joystick hard forward from centre in one quick motion. Repeat 10 times, 2 s apart.
4. On a computer, step through the video frame by frame. For each push, count frames from the first frame the
   joystick visibly moves to the first frame a wheel visibly turns.
5. Latency = frames ÷ fps (for example 12 frames at 240 fps = 50 ms). Write down the median and the worst.

## Results

| Path | Target | p50 | p95 | n | Date, setup |
|---|---|---|---|---|---|
| Joystick → movement | < 100 ms | not measured | | | slow-motion video, see above |
| Beat → lights | < 100 ms | not measured | | | |
| Object → map | < 500 ms | not measured | | | |
| New object → role announced | a few seconds | not measured | | | stopwatch from drop to narration |
| Song → transition starts | 5–15 s | not measured | | | |
| Song → new world | 5–15 s | not measured | | | |
| Robot camera → restyled frame | comfortable to drive | not measured | | | `video.status.latency_ms` on the status page |

Fill this in during the first hour at the venue: run the launcher, run the script for 2 minutes per path,
paste its table here with the date and setup (mic or cable, Jetson or replay, venue wifi or hotspot).
