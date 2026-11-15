"""Vision service: the robot's camera -> `vision.state` on the hub at up to VISION_HZ (T44).

    python -m vision                               # frames from the phone, via the eye page and the hub
    python -m vision --camera 0                    # a camera on this machine instead (development)
    python -m vision --file run.mp4 --no-giants    # a recorded clip

Runs on the laptop, next to the hub. Pipeline per frame:
    frame -> detect -> tracker -> re-id by appearance -> view coords (build_state)
    giant detector (hands and people reaching into the view) unless --no-giants
Also publishes `system.health` every 2 s and serves `/snapshot.jpg` (T45) unless --no-snapshot.
On `system.reset` the tracker, re-id gallery and giant ids are cleared.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import threading
import time

from server.common.config import load_config
from server.common.hub_client import HubClient

from vision.giants import GiantDetector
from vision.reid import ReId
from vision.state import GiantIds, build_state
from vision.tracker import Tracker

log = logging.getLogger("vision")
HEALTH_INTERVAL_S = 2.0
TRACK_MIN_HITS = 3        # a box must be seen in 3 frames before it is an object (no one-frame ghosts)
PERSON_CONF = 0.4


class NullDetector:
    """Stands in when the model can't be loaded, so giants and the snapshot still work."""

    def __init__(self, reason: str):
        self.reason = reason

    def detect_all(self, frame):
        return []

    def detect(self, frame, raw=None):
        return []


class Pipeline:
    """Everything that happens to one frame. Thread-safe enough for one worker thread plus readers."""

    def __init__(self, config: dict, detector, giants: bool = True):
        self.config = config
        self.detector = detector
        self.tracker = Tracker(min_hits=TRACK_MIN_HITS)
        self.reid = ReId(config)
        self.giants = GiantDetector() if giants else None
        self.giant_ids = GiantIds()
        self.lock = threading.Lock()
        self.privacy_boxes: list[list[float]] = []   # person/hand boxes, blurred by the snapshot server
        self.state: dict | None = None
        self.frames = 0
        self._reset_requested = False

    def request_reset(self) -> None:
        self._reset_requested = True

    def _reset(self) -> None:
        self.tracker.reset()
        self.reid.reset()
        self.giant_ids.reset()
        if self.giants:
            self.giants.reset()
        self._reset_requested = False
        log.info("vision state reset")

    def process(self, frame, ts: float, client_ts: float | None = None) -> dict:
        if self._reset_requested:
            self._reset()
        raw = self.detector.detect_all(frame)
        dets = self.detector.detect(frame, raw=raw)
        persons = [d for d in raw if d.cls == "person" and d.conf >= PERSON_CONF]

        tracks = self.reid.apply(self.tracker.update(dets, ts), ts, frame)
        giants = self.giants.detect(frame, persons) if self.giants else []
        giants = self.giant_ids.assign(giants, ts)

        state = build_state(tracks, giants, frame.shape, ts, client_ts)
        with self.lock:
            self.privacy_boxes = [g["bbox"] for g in giants] + [p.bbox for p in persons]
            self.state = state
            self.frames += 1
        return state


def default_hub_url(config: dict) -> str:
    scheme = "wss" if config.get("TLS_CERT") and config.get("TLS_KEY") else "ws"
    return f"{scheme}://127.0.0.1:{config['HUB_PORT']}/hub"


def make_detector(args):
    try:
        import ultralytics  # noqa: F401  (fail here, not on the first frame)
    except ImportError:
        log.error("ultralytics is not installed (pip install ultralytics): running without object detection")
        return NullDetector("ultralytics not installed")
    from vision.detector import Detector

    return Detector(model_path=args.model, imgsz=args.imgsz)


async def amain(args) -> None:
    config = load_config()
    detector = make_detector(args)
    pipeline = Pipeline(config, detector, giants=not args.no_giants)

    hub = await HubClient.connect(args.hub, "vision")
    if args.camera is not None or args.file:
        from vision.camera import Camera

        source = Camera(config, index=args.camera if args.camera is not None else 0, file=args.file)
        source_name = f"file {args.file}" if args.file else f"camera {args.camera}"
    else:
        from vision.frames import HubFrames

        source = HubFrames()
        hub.sub("camera.frame", source.on_envelope)
        source_name = "phone (camera.frame from the eye page)"
    hub.sub("system.reset", lambda env: pipeline.request_reset())
    log.info("connected to hub %s; frames from %s", args.hub, source_name)

    if not args.no_snapshot:
        from vision.snapshot_server import SnapshotServer

        def regions():
            with pipeline.lock:
                return list(pipeline.privacy_boxes)

        snap = SnapshotServer(source.latest, regions, host=args.snapshot_host,
                              port=int(config.get("VISION_HTTP_PORT", 8080)))
        snap.start()

    period = 1.0 / float(config.get("VISION_HZ", 10))
    next_pub = time.monotonic()
    next_health = time.monotonic() + HEALTH_INTERVAL_S
    fps_frames, fps_t0, fps = 0, time.monotonic(), 0.0
    no_model = getattr(detector, "reason", None)
    try:
        while True:
            try:
                ts, frame = await asyncio.to_thread(source.read, 5.0)
            except TimeoutError:
                await hub.pub("system.health", {"service": "vision", "ok": False,
                                                "detail": "no camera frames (is the eye page open and the "
                                                          "phone streaming?)"})
                continue
            state = await asyncio.to_thread(pipeline.process, frame, ts, getattr(source, "read_client_ts", None))
            fps_frames += 1
            now = time.monotonic()
            if now - fps_t0 >= 1.0:
                fps, fps_frames, fps_t0 = fps_frames / (now - fps_t0), 0, now
            if now >= next_pub:
                await hub.pub("vision.state", state)
                next_pub = max(next_pub + period, now)  # drift-free, but never bursts to catch up
            if now >= next_health:
                next_health = now + HEALTH_INTERVAL_S
                detail = (f"{fps:.1f} fps, {len(state['objects'])} in view, "
                          f"{pipeline.reid.remembered} remembered out of view")
                if no_model:
                    detail = f"no object detection ({no_model}); " + detail
                await hub.pub("system.health", {"service": "vision", "ok": fps >= 3 and not no_model,
                                                "detail": detail})
    finally:
        source.stop()
        await hub.close()


def main() -> None:
    config = load_config()
    p = argparse.ArgumentParser(prog="python -m vision", description="Genrator vision (robot's camera)")
    p.add_argument("--hub", default=os.environ.get("GENRATOR_HUB_URL", default_hub_url(config)))
    p.add_argument("--camera", default=None, help="read a camera on this machine (index or device path) "
                                                  "instead of the phone's frames")
    p.add_argument("--file", help="read frames from a video file instead of the phone")
    p.add_argument("--model", default=None, help="YOLO model path (default vision/models/yolo11n-seg.pt, "
                                                  "or its OpenVINO export there if present)")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--no-giants", action="store_true")
    p.add_argument("--no-snapshot", action="store_true")
    p.add_argument("--snapshot-host", default="127.0.0.1",
                   help="address the snapshot server listens on (default: this machine only)")
    args = p.parse_args()
    logging.basicConfig(level=os.environ.get("GENRATOR_LOG_LEVEL", "INFO").upper(),
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    try:
        asyncio.run(amain(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
