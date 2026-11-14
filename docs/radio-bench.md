# Radio contention bench (T24)

The gamepad (D packets, 25 Hz) and the bridge (L / R / V packets) share one micro:bit radio group and
channel. This bench checks that light traffic from the laptop does not make driving laggy or lossy.

## Setup
1. Bridge micro:bit on the laptop USB, flashed with `firmware/bridge/main.py`.
2. Spare micro:bit A flashed with `firmware/bench/echo.py` (stands in for the Cutebot).
3. Optional, for true two-sender contention: spare micro:bit B flashed with `firmware/gamepad/drive.py`
   (stick centred, it sends zeros at 25 Hz) and run with `--drive-source gamepad`.
4. All three on the same `RADIO_GROUP` / `RADIO_CHANNEL`.

## Run
```
python scripts/radio_bench.py --port /dev/ttyACM0 --rates 0,5,10,20 --seconds 10 --drive-source laptop
python scripts/radio_bench.py --port /dev/ttyACM0 --rates 0,5,10,20 --seconds 10 --drive-source gamepad
```
`laptop` mode measures true round-trip time and loss. `gamepad` mode measures loss from sequence gaps and
uses the gap between echoes as a latency proxy (one-way time is not observable from the laptop).

## Results
**Not yet measured** - needs the spare micro:bits. Paste the script's tables here.

| light Hz | loss % | p50 ms | p95 ms | max ms |
|---|---|---|---|---|
| 0 (baseline) | | | | |
| 5 | | | | |
| 10 | | | | |
| 20 | | | | |

## Chosen `LIGHT_MAX_HZ`
**10** (provisional default from T01). Replace with the highest rate whose loss and p95 stay within about
10 % / 20 ms of the 0 Hz baseline, and say why. Update `shared/config.json` if it changes.
