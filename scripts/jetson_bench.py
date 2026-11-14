"""Detector + tracker FPS benchmark for the Jetson (T46).

    python3 scripts/jetson_bench.py                          # PyTorch .pt vs TensorRT .engine, at 640 and 960
    python3 scripts/jetson_bench.py --file table.mp4         # use a recorded clip instead of the camera
    python3 scripts/jetson_bench.py --models jetson/models/yolo11n.engine --sizes 640

Frames come from the overhead camera (or --file, or a synthetic frame with --synthetic). Each run warms up,
then times detect + track for --frames frames and prints a markdown table to paste into docs/jetson-setup.md.
Note: a TensorRT engine has a fixed input size, so a size other than the one it was exported at is skipped.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from jetson.detector import MODEL_NAME, MODELS_DIR, Detector  # noqa: E402
from jetson.tracker import Tracker  # noqa: E402


def frames_source(args):
    if args.synthetic:
        rng = np.random.default_rng(0)
        frame = rng.integers(0, 255, (720, 1280, 3), dtype=np.uint8)
        return lambda: frame, lambda: None
    from jetson.camera import Camera

    cam = Camera(index=args.camera, file=args.file)
    return (lambda: cam.read()[1]), cam.stop


def bench(model_path: str, imgsz: int, next_frame, n: int, warmup: int) -> dict:
    det = Detector(model_path=model_path, imgsz=imgsz)
    tracker = Tracker()
    for _ in range(warmup):
        det.detect(next_frame())
    times, counts = [], []
    for i in range(n):
        frame = next_frame()
        t0 = time.perf_counter()
        dets = det.detect(frame)
        tracker.update(dets, time.time())
        times.append(time.perf_counter() - t0)
        counts.append(len(dets))
    t = np.array(times)
    return {"model": Path(model_path).name, "imgsz": imgsz, "fps": 1 / t.mean(),
            "p50_ms": np.percentile(t, 50) * 1000, "p95_ms": np.percentile(t, 95) * 1000,
            "objects": float(np.mean(counts))}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--models", nargs="+",
                   default=[str(MODELS_DIR / f"{MODEL_NAME}.pt"), str(MODELS_DIR / f"{MODEL_NAME}.engine")])
    p.add_argument("--sizes", nargs="+", type=int, default=[640, 960])
    p.add_argument("--frames", type=int, default=200)
    p.add_argument("--warmup", type=int, default=20)
    p.add_argument("--camera", default=0)
    p.add_argument("--file")
    p.add_argument("--synthetic", action="store_true")
    args = p.parse_args()

    next_frame, stop = frames_source(args)
    rows = []
    try:
        for model in args.models:
            if model.endswith(".engine") and not Path(model).exists():
                print(f"skip {model}: not exported yet (scripts/jetson_export.sh)")
                continue
            for size in args.sizes:
                try:
                    r = bench(model, size, next_frame, args.frames, args.warmup)
                except Exception as exc:  # e.g. engine built for another input size
                    print(f"skip {Path(model).name} @ {size}: {exc}")
                    continue
                rows.append(r)
                print(f"{r['model']:>16} @ {size}: {r['fps']:.1f} fps (p95 {r['p95_ms']:.0f} ms)")
    finally:
        stop()

    print("\n| Model | Input | FPS (detect+track) | p50 ms | p95 ms | Objects/frame |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['model']} | {r['imgsz']} | {r['fps']:.1f} | {r['p50_ms']:.0f} | {r['p95_ms']:.0f} | {r['objects']:.1f} |")


if __name__ == "__main__":
    main()
