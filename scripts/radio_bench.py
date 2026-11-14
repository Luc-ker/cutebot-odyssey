#!/usr/bin/env python3
"""T24 - radio contention bench: does light/recoil traffic hurt driving?

Setup (see docs/radio-bench.md): bridge micro:bit on USB; a SPARE micro:bit running firmware/bench/echo.py
stands in for the Cutebot (answers D,..,seq with T,seq,0,0,0).

Two ways to produce the D traffic:
  --drive-source laptop   the laptop sends D through the bridge itself -> true round trip time + loss
  --drive-source gamepad  a second spare micro:bit runs gamepad/drive.py (real contention from a second
                          radio sender); the laptop only listens -> loss from seq gaps, and p95 of the
                          gap between echoes as a latency proxy (one-way time is not observable)
For each rate in --rates the laptop also sends L packets at that many Hz through the bridge.

    python scripts/radio_bench.py --port /dev/ttyACM0 --rates 0,5,10,20 --seconds 10
"""
import argparse
import json
import os
import statistics
import time


def load_drive_hz():
    try:
        p = os.path.join(os.path.dirname(__file__), "..", "shared", "config.json")
        with open(p) as f:
            return int(json.load(f).get("DRIVE_HZ", 25))
    except Exception:
        return 25


def pct(vals, q):
    if not vals:
        return float("nan")
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * len(s)))]


def run_rate(ser, rate_hz, seconds, source, drive_hz):
    ser.reset_input_buffer()
    sent_at, rtts, arrivals, seen = {}, [], [], []
    seq = n_sent = 0
    colour = 0
    t0 = time.monotonic()
    next_d = next_l = t0
    buf = b""
    while time.monotonic() - t0 < seconds:
        now = time.monotonic()
        if source == "laptop" and now >= next_d:
            ser.write(("D,0,0,%d\n" % seq).encode())
            sent_at[seq] = now
            seq = (seq + 1) & 255
            n_sent += 1
            next_d += 1.0 / drive_hz
        if rate_hz and now >= next_l:
            colour = (colour + 40) & 255
            ser.write(("L,F,%d,0,0,50\n" % colour).encode())
            next_l += 1.0 / rate_hz
        buf += ser.read(256)
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            p = line.decode("ascii", "ignore").strip().split(",")
            if len(p) == 5 and p[0] == "T":
                s, tr = int(p[1]), time.monotonic()
                arrivals.append(tr)
                seen.append(s)
                if source == "laptop" and s in sent_at:
                    rtts.append((tr - sent_at.pop(s)) * 1000)
        time.sleep(0.001)
    if source == "laptop":
        lost = len(sent_at)  # never echoed
        total = n_sent
        lat = rtts
    else:  # count missing seqs in the (wrapped) sequence we saw
        total = lost = 0
        for a, b in zip(seen, seen[1:]):
            gap = (b - a) & 255
            if 0 < gap < 128:
                total += gap
                lost += gap - 1
        gaps = [(y - x) * 1000 for x, y in zip(arrivals, arrivals[1:])]
        lat = gaps
    return {"rate": rate_hz, "total": total, "lost": lost,
            "loss_pct": 100.0 * lost / total if total else float("nan"),
            "p50": statistics.median(lat) if lat else float("nan"), "p95": pct(lat, 0.95),
            "max": max(lat) if lat else float("nan")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--rates", default="0,5,10,20")
    ap.add_argument("--seconds", type=float, default=10)
    ap.add_argument("--drive-source", choices=["laptop", "gamepad"], default="laptop")
    args = ap.parse_args()
    import serial
    ser = serial.Serial(args.port, 115200, timeout=0)
    drive_hz = load_drive_hz()
    what = "round trip ms" if args.drive_source == "laptop" else "echo gap ms (proxy)"
    print("| light Hz | D sent/seen | lost | loss %% | p50 %s | p95 | max |" % what)
    print("|---|---|---|---|---|---|---|")
    for r in [int(x) for x in args.rates.split(",")]:
        m = run_rate(ser, r, args.seconds, args.drive_source, drive_hz)
        print("| %d | %d | %d | %.1f | %.0f | %.0f | %.0f |" %
              (m["rate"], m["total"], m["lost"], m["loss_pct"], m["p50"], m["p95"], m["max"]))


if __name__ == "__main__":
    main()
