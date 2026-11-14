"""Play fake or recorded `vision.state` into the hub, so everything can be built without the Jetson (T47).

    python scripts/vision_replay.py scenes/robot_loop.json             # synthetic scene, looped
    python scripts/vision_replay.py my_run.jsonl --once                 # a recording, played once
    python scripts/vision_replay.py --record my_run.jsonl               # record live vision.state
    options: --hub ws://localhost:8765/hub  --speed 2  --once

Keys while replaying (in a terminal): space = pause/resume, g = a hand reaches in from a random edge, q = quit.

Scene JSON (see scripts/scenes/): positions are normalised table coords, times in seconds.
    {"name", "duration_s", "hz": 10,
     "objects": [{"id", "cls", "size": [w, h], "path": [[t, [x, y]], ...], "appear": t?, "remove": t?}],
     "robot":   {"path": [[t, [x, y]], ...]}  or  {"circle": {"centre": [x, y], "radius": r, "period_s": s}},
     "giants":  [{"id", "kind", "edge", "size": [w, h], "path": [[t, [x, y]], ...]}]}   # present during its path
Recordings are JSONL lines {"t": seconds since start, "data": <vision.state>}: state only, never images.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import sys
import time
from pathlib import Path
from typing import Awaitable, Callable

ROOT = Path(__file__).resolve().parents[1]
SCENES_DIR = Path(__file__).resolve().parent / "scenes"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

Frame = tuple[float, dict]   # (seconds since start, vision.state data)


# ---------------------------------------------------------------------------- scenes

def _clamp01(v: float) -> float:
    return min(max(float(v), 0.0), 1.0)


def interp(path: list, t: float) -> list[float]:
    """Linear interpolation along [[t, [x, y]], ...]; holds the ends."""
    if t <= path[0][0]:
        return list(path[0][1])
    for (t0, p0), (t1, p1) in zip(path, path[1:]):
        if t0 <= t <= t1:
            a = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return [p0[0] + a * (p1[0] - p0[0]), p0[1] + a * (p1[1] - p0[1])]
    return list(path[-1][1])


def _robot_at(robot: dict, t: float, duration: float) -> tuple[list[float], float]:
    if "circle" in robot:
        c = robot["circle"]
        w = 2 * math.pi / float(c.get("period_s", 10))
        ang = w * t
        pos = [c["centre"][0] + c["radius"] * math.cos(ang), c["centre"][1] + c["radius"] * math.sin(ang)]
        heading = ang + math.pi / 2  # tangent, moving clockwise on screen (y down)
    else:
        path = robot["path"]
        pos = interp(path, t)
        ahead = interp(path, min(t + 0.1, path[-1][0]))
        behind = interp(path, max(t - 0.1, path[0][0]))
        dx, dy = ahead[0] - behind[0], ahead[1] - behind[1]
        heading = math.atan2(dy, dx) if (dx or dy) else float(robot.get("heading", 0.0))
    heading = math.atan2(math.sin(heading), math.cos(heading))
    return [_clamp01(pos[0]), _clamp01(pos[1])], heading


def state_at(scene: dict, t: float, extra_giants: list[dict] | None = None) -> dict:
    objects = []
    for o in scene.get("objects", []):
        if t < o.get("appear", 0) or (o.get("remove") is not None and t >= o["remove"]):
            continue
        pos = interp(o["path"], t)
        objects.append({"id": int(o["id"]), "cls": o["cls"], "pos": [_clamp01(pos[0]), _clamp01(pos[1])],
                        "size": [_clamp01(v) for v in o.get("size", [0.08, 0.08])],
                        "conf": float(o.get("conf", 0.9))})
    robot = None
    if scene.get("robot"):
        r = scene["robot"]
        hidden = any(a <= t < b for a, b in r.get("hidden", []))
        pos, heading = _robot_at(r, t, scene.get("duration_s", 10))
        robot = {"pos": pos, "heading": heading, "seen": not hidden}
    giants = []
    for g in list(scene.get("giants", [])) + list(extra_giants or []):
        if not (g["path"][0][0] <= t <= g["path"][-1][0]):
            continue
        pos = interp(g["path"], t)
        giants.append({"id": g["id"], "kind": g.get("kind", "hand"), "pos": [_clamp01(pos[0]), _clamp01(pos[1])],
                       "size": [_clamp01(v) for v in g.get("size", [0.15, 0.1])], "edge": g["edge"]})
    return {"frame_ts": 0.0, "objects": objects, "robot": robot, "giants": giants}


def scene_frames(scene: dict) -> list[Frame]:
    hz = float(scene.get("hz", 10))
    n = max(1, int(round(float(scene.get("duration_s", 10)) * hz)))
    return [(i / hz, state_at(scene, i / hz)) for i in range(n)]


def load_frames(path: str | Path) -> tuple[list[Frame], dict | None]:
    """Frames from a scene (.json) or a recording (.jsonl). Returns (frames, scene or None)."""
    p = Path(path)
    if not p.exists() and (SCENES_DIR / p.name).exists():
        p = SCENES_DIR / p.name
    if p.suffix == ".jsonl":
        frames = []
        for line in p.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                frames.append((float(rec["t"]), rec["data"]))
        return frames, None
    scene = json.loads(p.read_text())
    return scene_frames(scene), scene


def hand_from(edge: str, start: float, gid: str) -> dict:
    """A hand that reaches 0.25 in from `edge` and back over 2 s, starting at scene time `start`."""
    y = random.uniform(0.25, 0.75)
    outside, inside = {
        "left": ([0.0, y], [0.25, y]), "right": ([1.0, y], [0.75, y]),
        "top": ([y, 0.0], [y, 0.25]), "bottom": ([y, 1.0], [y, 0.75]),
    }[edge]
    return {"id": gid, "kind": "hand", "edge": edge, "size": [0.15, 0.12],
            "path": [[start, outside], [start + 0.8, inside], [start + 1.2, inside], [start + 2.0, outside]]}


# ---------------------------------------------------------------------------- replay

class Controls:
    def __init__(self):
        self.paused = False
        self.quit = False
        self.inject_hand = False


async def replay(frames: list[Frame], publish: Callable[[dict], Awaitable[None]], *, loop: bool = False,
                 speed: float = 1.0, controls: Controls | None = None, scene: dict | None = None,
                 clock: Callable[[], float] = time.monotonic, wall: Callable[[], float] = time.time) -> int:
    """Publish frames at their recorded spacing. Returns the number of messages published."""
    controls = controls or Controls()
    if not frames:
        return 0
    period_end = frames[-1][0] + (frames[-1][0] - frames[-2][0] if len(frames) > 1 else 0.1)
    extra: list[dict] = []
    hand_n = 0
    sent = 0
    offset = 0.0  # scene time of the start of this pass (grows on loop)
    start = clock()
    paused_at = None
    while not controls.quit:
        for t, data in frames:
            due = start + (offset + t) / speed
            while True:
                if controls.quit:
                    return sent
                if controls.paused:
                    paused_at = paused_at or clock()
                    await asyncio.sleep(0.05)
                    continue
                if paused_at is not None:  # shift the schedule by the time spent paused
                    start += clock() - paused_at
                    due = start + (offset + t) / speed
                    paused_at = None
                delay = due - clock()
                if delay <= 0:
                    break
                await asyncio.sleep(min(delay, 0.05))
            if controls.inject_hand and scene is not None:
                controls.inject_hand = False
                hand_n += 1
                extra.append(hand_from(random.choice(["left", "right", "top", "bottom"]), t, f"g9{hand_n}"))
            if extra and scene is not None:
                extra = [g for g in extra if g["path"][-1][0] >= t]
                data = state_at(scene, t, extra)
            out = dict(data)
            out["frame_ts"] = wall()
            await publish(out)
            sent += 1
        if not loop:
            break
        offset += period_end
    return sent


def _keyboard(controls: Controls) -> None:
    """Read single keys from a terminal in a background thread."""
    if not sys.stdin.isatty():
        return
    import termios
    import threading
    import tty

    def run():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while not controls.quit:
                ch = sys.stdin.read(1)
                if ch == " ":
                    controls.paused = not controls.paused
                    print("paused" if controls.paused else "playing", flush=True)
                elif ch == "g":
                    controls.inject_hand = True
                    print("hand!", flush=True)
                elif ch in ("q", "\x03"):
                    controls.quit = True
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    threading.Thread(target=run, daemon=True).start()


async def record(hub_url: str, out_path: str) -> None:
    from server.common.hub_client import HubClient

    hub = await HubClient.connect(hub_url, "vision-recorder")
    t0 = None
    n = 0
    with open(out_path, "w", encoding="utf-8") as f:
        def on_state(env):
            nonlocal t0, n
            now = time.monotonic()
            t0 = now if t0 is None else t0
            f.write(json.dumps({"t": round(now - t0, 4), "data": env["data"]}) + "\n")
            n += 1
            if n % 50 == 0:
                print(f"\r{n} states", end="", flush=True)

        hub.sub("vision.state", on_state)
        print(f"recording vision.state to {out_path}; Ctrl-C to stop")
        try:
            await asyncio.Event().wait()
        finally:
            await hub.close()


async def amain(args) -> None:
    if args.record:
        await record(args.hub, args.record)
        return
    frames, scene = load_frames(args.source)
    from server.common.hub_client import HubClient

    hub = await HubClient.connect(args.hub, "vision-replay")
    controls = Controls()
    _keyboard(controls)
    print(f"replaying {args.source}: {len(frames)} frames{' (looped)' if not args.once else ''}; "
          "space = pause, g = hand, q = quit")

    async def publish(data):
        await hub.pub("vision.state", data)

    try:
        await replay(frames, publish, loop=not args.once, speed=args.speed, controls=controls, scene=scene)
    finally:
        await hub.close()


def main() -> None:
    from server.common.config import load_config

    cfg = load_config()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", nargs="?", help="scene .json or recorded .jsonl")
    p.add_argument("--hub", default=f"ws://localhost:{cfg['HUB_PORT']}/hub")
    p.add_argument("--record", metavar="OUT.jsonl")
    p.add_argument("--once", action="store_true", help="play once instead of looping")
    p.add_argument("--speed", type=float, default=1.0)
    args = p.parse_args()
    if not args.record and not args.source:
        p.error("give a scene/recording to replay, or --record OUT.jsonl")
    try:
        asyncio.run(amain(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
