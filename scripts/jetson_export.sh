#!/usr/bin/env bash
# Export the YOLO detector to a TensorRT FP16 engine on the Jetson (T46).
#
#   scripts/jetson_export.sh [model] [imgsz]      # defaults: yolo11n 640
#
# Writes jetson/models/<model>.engine, which jetson/detector.py (T38) loads automatically when present.
# Must run ON the Jetson: TensorRT engines are tied to the GPU and TensorRT version they were built with.
set -euo pipefail

MODEL="${1:-yolo11n}"
IMGSZ="${2:-640}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$ROOT/jetson/models"
mkdir -p "$OUT_DIR"
cd "$OUT_DIR"

if ! python3 -c "import tensorrt" 2>/dev/null; then
  echo "TensorRT Python bindings not found. On JetPack they come with the system python3 (see docs/jetson-setup.md)." >&2
  exit 1
fi

# Ultralytics downloads <model>.pt here on first use, then exports <model>.engine next to it.
python3 - "$MODEL" "$IMGSZ" <<'PY'
import sys
from ultralytics import YOLO
model, imgsz = sys.argv[1], int(sys.argv[2])
path = YOLO(f"{model}.pt").export(format="engine", half=True, imgsz=imgsz, device=0, workspace=2)
print(f"engine written: {path}")
PY

echo "OK: $OUT_DIR/$MODEL.engine (imgsz $IMGSZ, FP16)"
echo "If you exported at an imgsz other than 640, run jetson.main with --imgsz $IMGSZ."
