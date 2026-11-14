"""Object detector for the overhead camera (T38, contract C8).

    det = Detector(calib=calib)
    det.detect(frame) -> list[Detection]        # useful table objects, pixel space, on the table only
    det.detect_all(frame) -> list[Detection]    # raw model output incl. "person" (for giants, T43)
    detect(frame)                               # module-level, uses a lazily created default Detector

Uses an Ultralytics YOLO model: the TensorRT engine `jetson/models/<MODEL>.engine` from T46 if it exists,
else `<MODEL>.pt` (downloaded by Ultralytics on first use). `filter_detections` is a pure function so the
filtering rules can be tested without a model.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

log = logging.getLogger("detector")

MODELS_DIR = Path(__file__).resolve().parent / "models"
MODEL_NAME = "yolo11n"
IMGSZ = 640
CONF_THRESHOLD = 0.35
MIN_BOX_PX = 12          # boxes smaller than this on either side are noise at 720p
MAX_BOX_FRACTION = 0.6   # a box covering most of the frame is the table itself, not an object

# COCO classes that are plausible on a table and useful as world objects.
USEFUL_CLASSES = frozenset({
    "cup", "bottle", "wine glass", "bowl", "book", "backpack", "handbag", "suitcase", "laptop", "cell phone",
    "chair", "scissors", "teddy bear", "remote", "mouse", "keyboard", "vase", "clock", "potted plant",
    "banana", "apple", "orange", "sports ball", "toothbrush", "umbrella", "shoe", "tie", "fork", "knife",
    "spoon", "sandwich", "donut", "cake", "broccoli", "carrot", "frisbee", "toy car",
})


@dataclass
class Detection:
    bbox: list[float]            # [x1, y1, x2, y2] in pixels
    cls: str
    conf: float
    extra: dict = field(default_factory=dict)

    @property
    def centre(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return (x1 + x2) / 2, (y1 + y2) / 2


def filter_detections(raw: Iterable[Detection], calib=None, frame_shape: Sequence[int] | None = None,
                      conf: float = CONF_THRESHOLD, min_box: float = MIN_BOX_PX,
                      classes: frozenset[str] = USEFUL_CLASSES) -> list[Detection]:
    """Keep confident, reasonably sized, useful-class detections that overlap the table."""
    out = []
    frame_area = frame_shape[0] * frame_shape[1] if frame_shape is not None else None
    for d in raw:
        if d.cls not in classes or d.conf < conf:
            continue
        x1, y1, x2, y2 = d.bbox
        w, h = x2 - x1, y2 - y1
        if w < min_box or h < min_box:
            continue
        if frame_area and w * h > MAX_BOX_FRACTION * frame_area:
            continue
        if calib is not None and not calib.box_overlaps_table(d.bbox):
            continue
        out.append(d)
    return out


def default_model_path(name: str = MODEL_NAME) -> str:
    engine = MODELS_DIR / f"{name}.engine"
    if engine.exists():
        return str(engine)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return str(MODELS_DIR / f"{name}.pt")  # Ultralytics downloads it here on first use


class Detector:
    def __init__(self, model_path: str | None = None, calib=None, imgsz: int = IMGSZ,
                 conf: float = CONF_THRESHOLD, device: str | int | None = None, half: bool | None = None):
        self.model_path = model_path or default_model_path()
        self.calib = calib
        self.imgsz = imgsz
        self.conf = conf
        self.device = device
        self.half = half
        self._model = None

    def _load(self):
        if self._model is None:
            from ultralytics import YOLO  # heavy import, only when actually detecting

            log.info("loading detector %s", self.model_path)
            self._model = YOLO(self.model_path, task="detect")
        return self._model

    def detect_all(self, frame: np.ndarray) -> list[Detection]:
        """Raw model detections (every class, low threshold) in pixel space."""
        model = self._load()
        kw = {"imgsz": self.imgsz, "conf": min(self.conf, 0.25), "verbose": False}
        if self.device is not None:
            kw["device"] = self.device
        if self.half is not None:
            kw["half"] = self.half
        result = model.predict(frame, **kw)[0]
        names = result.names
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []
        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        clss = boxes.cls.cpu().numpy().astype(int)
        return [Detection([float(v) for v in b], names[c], float(p)) for b, p, c in zip(xyxy, confs, clss)]

    def detect(self, frame: np.ndarray, raw: list[Detection] | None = None) -> list[Detection]:
        """Useful table objects. Pass `raw` (from detect_all) to avoid running the model twice."""
        raw = self.detect_all(frame) if raw is None else raw
        return filter_detections(raw, self.calib, frame.shape, conf=self.conf)


_default: Detector | None = None


def detect(frame: np.ndarray) -> list[Detection]:
    global _default
    if _default is None:
        _default = Detector()
    return _default.detect(frame)
