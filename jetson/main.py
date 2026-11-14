"""Jetson main loop: overhead camera -> `vision.state` on the hub at VISION_HZ (T44).

    python -m jetson.main --hub ws://<laptop>:8765/hub
    python -m jetson.main --file table.mp4 --no-giants        # from a recorded clip

Pipeline per frame:
    camera -> detect (+ generic detect if available) -> drop detections overlapping the robot
           -> tracker -> re-id -> table coords (build_state)
    robot marker -> pose filter;   giant detector (unless --no-giants)
Also publishes `system.health` every 2 s and serves `/snapshot.jpg` (T45) unless --no-snapshot.
On `system.reset` the tracker, re-id, pose and backgrounds are cleared.

Over the USB-C cable the laptop is 192.168.55.100 as seen from the Jetson, which is the default hub host.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import threading
import time
from pathlib import Path

from server.common.config import load_config
from server.common.hub_client import HubClient

from jetson.calibration import DEFAULT_PATH as CALIB_PATH, Calibration
from jetson.camera import Camera
from jetson.giants import GiantDetector
from jetson.reid import ReId
from jetson.robot_marker import find_robot
from jetson.robot_pose import RobotPose
from jetson.state import GiantIds, build_state, overlaps_robot
from jetson.tracker import Tracker

log = logging.getLogger("jetson")
USB_HOST_IP = "192.168.55.100"
HEALTH_INTERVAL_S = 2.0


def _generic_detector_class():
    try:  # T110, optional
        from jetson.generic_detector import GenericDetector
        return GenericDetector
    except ImportError:
        return None


class Pipeline:
    """Everything that happens to one frame. Thread-safe enough for one worker thread plus readers."""

    def __init__(self, config: dict, calib: Calibration | None, detector, giants: bool = True, generic: bool = True):
        self.config = config
        self.calib = calib
        self.detector = detector
        self.tracker = Tracker()
        self.reid = ReId(config, calib)
        self.pose = RobotPose(calib) if calib is not None else None
        self.giants = GiantDetector(calib) if giants else None
        self.giant_ids = GiantIds()
        gen_cls = _generic_detector_class() if generic else None
        self.generic = gen_cls() if gen_cls else None
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
        if self.pose:
            self.pose.reset()
        if self.giants:
            self.giants.reset()
        if self.generic and hasattr(self.generic, "reset"):
            self.generic.reset()
        self._reset_requested = False
        log.info("vision state reset")

    def process(self, frame, ts: float) -> dict:
        if self.calib is None:  # no calibration file: the whole frame is the table
            h, w = frame.shape[:2]
            self.calib = Calibration.identity(w, h)
            self.reid.calib = self.calib
            self.pose = RobotPose(self.calib)
            if self.giants:
                self.giants.calib = self.calib
            self.detector.calib = self.calib
        if self._reset_requested:
            self._reset()

        raw = self.detector.detect_all(frame)
        dets = self.detector.detect(frame, raw=raw)
        persons = [d for d in raw if d.cls == "person" and d.conf >= 0.4]

        marker = find_robot(frame)
        robot_bbox = marker["bbox"] if marker else None
        if self.generic is not None:
            try:
                dets += self.generic.detect(frame, dets)
            except Exception:  # an optional extra must never stop the main loop
                log.exception("generic detector failed")
        dets = [d for d in dets if not overlaps_robot(d.bbox, robot_bbox)]

        tracks = self.reid.apply(self.tracker.update(dets, ts), ts, frame)
        pose = self.pose.update(marker, ts)
        giants = self.giants.detect(frame, self.calib, persons) if self.giants else []
        giants = self.giant_ids.assign(giants, ts)

        state = build_state(tracks, pose, giants, self.calib, ts, robot_bbox)
        with self.lock:
            self.privacy_boxes = [g["bbox"] for g in giants] + [p.bbox for p in persons]
            self.state = state
            self.frames += 1
        return state


async def amain(args) -> None:
    config = load_config()
    calib = Calibration.load(args.calib) if Path(args.calib).exists() else None
    if calib is None:
        log.warning("no calibration at %s: using the whole frame as the table (run jetson.calibrate_tool)", args.calib)

    from jetson.detector import Detector

    detector = Detector(model_path=args.model, calib=calib, imgsz=args.imgsz)
    pipeline = Pipeline(config, calib, detector, giants=not args.no_giants, generic=not args.no_generic)
    cam = Camera(config, index=args.camera, file=args.file)

    if not args.no_snapshot:
        from jetson.snapshot_server import SnapshotServer

        def regions():
            with pipeline.lock:
                return list(pipeline.privacy_boxes)

        snap = SnapshotServer(cam.latest, regions, lambda: pipeline.calib, config,
                              port=int(config["JETSON_HTTP_PORT"]))
        snap.start()

    hub = await HubClient.connect(args.hub, "jetson")
    hub.sub("system.reset", lambda env: pipeline.request_reset())
    log.info("connected to hub %s", args.hub)

    period = 1.0 / float(config.get("VISION_HZ", 10))
    next_pub = time.monotonic()
    next_health = time.monotonic() + HEALTH_INTERVAL_S
    fps_frames, fps_t0, fps = 0, time.monotonic(), 0.0
    try:
        while True:
            try:
                ts, frame = await asyncio.to_thread(cam.read, 5.0)
            except TimeoutError:
                await hub.pub("system.health", {"service": "vision", "ok": False, "detail": "no camera frames"})
                continue
            state = await asyncio.to_thread(pipeline.process, frame, ts)
            fps_frames += 1
            now = time.monotonic()
            if now - fps_t0 >= 1.0:
                fps, fps_frames, fps_t0 = fps_frames / (now - fps_t0), 0, now
            if now >= next_pub:
                await hub.pub("vision.state", state)
                next_pub = max(next_pub + period, now)  # drift-free, but never bursts to catch up
            if now >= next_health:
                next_health = now + HEALTH_INTERVAL_S
                await hub.pub("system.health", {
                    "service": "vision", "ok": fps >= 5,
                    "detail": f"{fps:.1f} fps, {len(state['objects'])} objects, "
                              f"robot {'seen' if state['robot'] and state['robot']['seen'] else 'lost'}"})
    finally:
        cam.stop()
        await hub.close()


def main() -> None:
    config = load_config()
    p = argparse.ArgumentParser(description="Genrator overhead vision")
    p.add_argument("--hub", default=os.environ.get("GENRATOR_HUB_URL", f"ws://{USB_HOST_IP}:{config['HUB_PORT']}/hub"))
    p.add_argument("--camera", default=0, help="camera index or device path")
    p.add_argument("--file", help="read frames from a video file instead of the camera")
    p.add_argument("--calib", default=str(CALIB_PATH))
    p.add_argument("--model", default=None, help="YOLO model or TensorRT engine path")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--no-giants", action="store_true")
    p.add_argument("--no-generic", action="store_true", help="skip the generic object detector (T110)")
    p.add_argument("--no-snapshot", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=os.environ.get("GENRATOR_LOG_LEVEL", "INFO").upper(),
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    try:
        asyncio.run(amain(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
