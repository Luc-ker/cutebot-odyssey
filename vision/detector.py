"""Object detector for the robot's camera (T38, contract C8).

    det = Detector()
    det.detect(frame) -> list[Detection]        # useful objects, pixel space
    det.detect_all(frame) -> list[Detection]    # raw model output incl. "person" (for giants, T43)
    detect(frame)                               # module-level, uses a lazily created default Detector

Uses an Ultralytics YOLO segmentation model: `vision/models/<MODEL>.pt` (downloaded by Ultralytics on first
use), or an export of it there if one exists: `<MODEL>.engine`, `<MODEL>_openvino_model/` (the fast choice on
Intel laptops, see docs/local-renderer.md) or `<MODEL>.onnx`. It runs on the laptop (CPU, Intel GPU via OpenVINO,
Apple MPS or CUDA). With a segmentation model each detection also carries `extra["outline"]`: up to
`OUTLINE_POINTS` [x, y] pixel points around the object, which the eye page's local renderer uses to cover it.
`filter_detections` and `resample_outline` are pure functions so they can be tested without a model.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

log = logging.getLogger("detector")

MODELS_DIR = Path(__file__).resolve().parent / "models"
MODEL_NAME = "yolo11n-seg"
IMGSZ = 640
CONF_THRESHOLD = 0.35
MIN_BOX_PX = 10          # boxes smaller than this on either side are noise
MAX_BOX_FRACTION = 0.9   # close up an object can fill most of the view; a box over all of it is the table
OUTLINE_POINTS = 24      # enough to follow a mug handle, small enough for 10 Hz messages

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


def filter_detections(raw: Iterable[Detection], frame_shape: Sequence[int] | None = None,
                      conf: float = CONF_THRESHOLD, min_box: float = MIN_BOX_PX,
                      classes: frozenset[str] = USEFUL_CLASSES) -> list[Detection]:
    """Keep confident, reasonably sized, useful-class detections."""
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
        out.append(d)
    return out


def resample_outline(points, n: int = OUTLINE_POINTS) -> list[list[float]]:
    """A mask contour (k x 2 pixel points) -> at most `n` points evenly spaced along it, rounded to 0.1 px."""
    if points is None or len(points) < 3:
        return []
    pts = np.asarray(points, dtype=float).reshape(-1, 2)
    if len(pts) > n:
        closed = np.vstack([pts, pts[:1]])
        dist = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(closed, axis=0), axis=1))])
        if dist[-1] <= 0:
            return []
        targets = np.linspace(0.0, dist[-1], n, endpoint=False)
        pts = np.column_stack([np.interp(targets, dist, closed[:, 0]), np.interp(targets, dist, closed[:, 1])])
    return [[round(float(x), 1), round(float(y), 1)] for x, y in pts]


def model_task(path: str) -> str:
    """Ultralytics task for a model path: segmentation models have "-seg" in their name."""
    return "segment" if "-seg" in Path(path).name else "detect"


def default_model_path(name: str = MODEL_NAME, models_dir: Path = MODELS_DIR) -> str:
    for exported in (models_dir / f"{name}.engine", models_dir / f"{name}_openvino_model",
                     models_dir / f"{name}.onnx"):
        if exported.exists():
            return str(exported)
    models_dir.mkdir(parents=True, exist_ok=True)
    return str(models_dir / f"{name}.pt")  # Ultralytics downloads it here on first use


class Detector:
    def __init__(self, model_path: str | None = None, imgsz: int = IMGSZ,
                 conf: float = CONF_THRESHOLD, device: str | int | None = None, half: bool | None = None):
        self.model_path = model_path or default_model_path()
        self.imgsz = imgsz
        self.conf = conf
        self.device = device
        self.half = half
        self._model = None

    def _load(self):
        if self._model is None:
            from ultralytics import YOLO  # heavy import, only when actually detecting

            log.info("loading detector %s", self.model_path)
            self._model = YOLO(self.model_path, task=model_task(self.model_path))
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
        masks = getattr(result, "masks", None)
        outlines = list(masks.xy) if masks is not None else []
        out = []
        for i, (b, p, c) in enumerate(zip(xyxy, confs, clss)):
            extra = {}
            outline = resample_outline(outlines[i]) if i < len(outlines) else []
            if outline:
                extra["outline"] = outline
            out.append(Detection([float(v) for v in b], names[c], float(p), extra))
        return out

    def detect(self, frame: np.ndarray, raw: list[Detection] | None = None) -> list[Detection]:
        """Useful objects. Pass `raw` (from detect_all) to avoid running the model twice."""
        raw = self.detect_all(frame) if raw is None else raw
        return filter_detections(raw, frame.shape, conf=self.conf)


_default: Detector | None = None


def detect(frame: np.ndarray) -> list[Detection]:
    global _default
    if _default is None:
        _default = Detector()
    return _default.detect(frame)
