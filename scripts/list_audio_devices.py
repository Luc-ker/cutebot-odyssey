"""List audio devices with their indexes, for AUDIO_DEVICE in shared/config.json (T64).

    python scripts/list_audio_devices.py          # input devices only
    python scripts/list_audio_devices.py --all    # outputs too

AUDIO_DEVICE takes either the index or a unique part of the name (e.g. "USB" or "MacBook").
"""

import argparse
import sys


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--all", action="store_true", help="also list output-only devices")
    args = p.parse_args(argv)
    try:
        import sounddevice as sd
    except ImportError:
        print("sounddevice is not installed: pip install sounddevice", file=sys.stderr)
        return 1

    devices = sd.query_devices()
    try:  # sd.default.device is an (input, output) pair object; -1 means "none"
        default_in, default_out = sd.default.device[0], sd.default.device[1]
    except (TypeError, IndexError):
        default_in, default_out = sd.default.device, None
    hostapis = sd.query_hostapis()
    print(f"{'idx':>3}  {'in':>3} {'out':>3}  {'rate':>6}  {'api':<12} name")
    shown = 0
    for i, d in enumerate(devices):
        if not args.all and d["max_input_channels"] < 1:
            continue
        mark = " *in" if i == default_in else (" *out" if i == default_out else "")
        api = hostapis[d["hostapi"]]["name"] if d["hostapi"] < len(hostapis) else "?"
        print(f"{i:>3}  {d['max_input_channels']:>3} {d['max_output_channels']:>3}  "
              f"{int(d['default_samplerate']):>6}  {api[:12]:<12} {d['name']}{mark}")
        shown += 1
    if not shown:
        print("no input devices found")
    print("\n* = system default. Set AUDIO_DEVICE to the idx or a unique part of the name.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
