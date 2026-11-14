"""T98 — measure Genrator's responsiveness against the whitepaper §10 targets.

    python scripts/latency.py                       # listen for 60 s, print p50/p95 per path
    python scripts/latency.py --seconds 120 --hub ws://127.0.0.1:8765/hub
    python scripts/latency.py --selftest            # check the maths on synthetic messages, no hub needed

Paths (times are when this script receives each message, so every path includes the same hub hop):

    beat -> lights      audio.beat  -> the next robot.cmd {kind: "lights"}             target < 100 ms
    object -> world     vision.state with an object moved -> world.objects showing it   target < 500 ms
    song -> world       you press Enter when the song changes -> world.current, new id  target 5-15 s
    song -> transition  same mark -> world.transition                                   (shown as it starts)

For "song -> world", run the launcher with ``--audio-file`` of two songs back to back (or play songs by hand)
and press Enter at the moment the music changes. Joystick -> movement never goes through the laptop; measure
it with a slow-motion phone video (see docs/latency.md).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BEAT_MATCH_S = 0.25        # a lights command later than this after a beat is not "for" that beat
MOVE_EPS = 0.01            # normalised units; smaller jitter is not a move
MAP_MATCH_EPS = 0.02       # world.objects pos within this of the moved-to pos counts as updated
MOVE_TIMEOUT_S = 3.0       # give up on a move that never shows in world.objects
SONG_TIMEOUT_S = 60.0

TARGETS = {
    "beat -> lights": "< 100 ms",
    "object -> world": "< 500 ms",
    "song -> world": "5-15 s",
    "song -> transition": "5-15 s",
}


def percentile(values: list[float], p: float) -> float:
    if not values:
        return math.nan
    s = sorted(values)
    k = (len(s) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _close(a, b, eps) -> bool:
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


class Latency:
    """Feed it (topic, data, receive_time); it collects delays per path in seconds."""

    def __init__(self):
        self.samples: dict[str, list[float]] = {k: [] for k in TARGETS}
        self.missed: dict[str, int] = {k: 0 for k in TARGETS}
        self._beats: list[float] = []
        self._last_pos: dict[int, list[float]] = {}
        self._moves: dict[int, tuple[list[float], float]] = {}  # id -> (new pos, time seen in vision)
        self._world_id: str | None = None
        self._mark: float | None = None
        self._mark_transition: float | None = None

    def mark_song_change(self, t: float) -> None:
        self._mark = t
        self._mark_transition = t

    def on(self, topic: str, data: dict, t: float) -> None:
        data = data or {}
        if topic == "audio.beat":
            self._beats.append(t)
            self._beats = [b for b in self._beats if t - b <= BEAT_MATCH_S]
        elif topic == "robot.cmd" and data.get("kind") == "lights":
            if self._beats:
                beat = self._beats.pop(0)
                self.samples["beat -> lights"].append(t - beat)
                self._beats.clear()  # one lights command per beat
        elif topic == "vision.state":
            for o in data.get("objects") or []:
                oid, pos = o.get("id"), o.get("pos")
                if oid is None or not pos:
                    continue
                prev = self._last_pos.get(oid)
                self._last_pos[oid] = pos
                if prev is not None and not _close(prev, pos, MOVE_EPS) and oid not in self._moves:
                    self._moves[oid] = (pos, t)
            for oid, (_, t0) in list(self._moves.items()):
                if t - t0 > MOVE_TIMEOUT_S:
                    del self._moves[oid]
                    self.missed["object -> world"] += 1
        elif topic == "world.objects":
            for o in data.get("objects") or []:
                m = self._moves.get(o.get("id"))
                if m and o.get("pos") and _close(m[0], o["pos"], MAP_MATCH_EPS):
                    self.samples["object -> world"].append(t - m[1])
                    del self._moves[o["id"]]
        elif topic == "world.current":
            wid = ((data.get("world") or {}).get("id"))
            if wid and wid != self._world_id:
                if self._mark is not None and self._world_id is not None:
                    self._settle("song -> world", t, "_mark")
                self._world_id = wid
        elif topic == "world.transition":
            if self._mark_transition is not None:
                self._settle("song -> transition", t, "_mark_transition")
        self._expire(t)

    def _settle(self, path: str, t: float, attr: str) -> None:
        mark = getattr(self, attr)
        if t - mark <= SONG_TIMEOUT_S:
            self.samples[path].append(t - mark)
        setattr(self, attr, None)

    def _expire(self, t: float) -> None:
        for path, attr in (("song -> world", "_mark"), ("song -> transition", "_mark_transition")):
            mark = getattr(self, attr)
            if mark is not None and t - mark > SONG_TIMEOUT_S:
                self.missed[path] += 1
                setattr(self, attr, None)

    def report(self) -> str:
        lines = [f"{'path':20} {'n':>5} {'p50':>10} {'p95':>10} {'max':>10}  target     missed"]
        for path, vals in self.samples.items():
            fmt = (lambda v: f"{v:.2f} s") if path.startswith("song") else (lambda v: f"{v * 1000:.0f} ms")
            if vals:
                cells = [fmt(percentile(vals, 50)), fmt(percentile(vals, 95)), fmt(max(vals))]
            else:
                cells = ["-", "-", "-"]
            lines.append(f"{path:20} {len(vals):>5} {cells[0]:>10} {cells[1]:>10} {cells[2]:>10}  "
                         f"{TARGETS[path]:10} {self.missed[path]}")
        return "\n".join(lines)


# --------------------------------------------------------------------------------------- live

async def listen(url: str, seconds: float, lat: Latency) -> None:
    import ssl

    import websockets

    ctx = None
    if url.startswith("wss://"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    loop = asyncio.get_running_loop()

    def keyboard():
        for _ in sys.stdin:
            t = time.monotonic()
            loop.call_soon_threadsafe(lat.mark_song_change, t)
            print("  song change marked", flush=True)

    threading.Thread(target=keyboard, daemon=True).start()
    topics = ["audio.beat", "robot.cmd", "vision.state", "world.objects", "world.current", "world.transition"]
    end = time.monotonic() + seconds
    async with websockets.connect(url, ssl=ctx, max_size=8 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"op": "sub", "topics": topics}))
        print(f"listening on {url} for {seconds:.0f} s; press Enter when the song changes", flush=True)
        while (left := end - time.monotonic()) > 0:
            try:
                raw = await asyncio.wait_for(ws.recv(), left)
            except asyncio.TimeoutError:
                break
            env = json.loads(raw)
            lat.on(env.get("topic", ""), env.get("data") or {}, time.monotonic())


def selftest() -> int:
    lat = Latency()
    t = 100.0
    for i in range(20):  # beats with lights 30–49 ms later
        lat.on("audio.beat", {"tempo_bpm": 120, "strength": 1}, t + i * 0.5)
        lat.on("robot.cmd", {"kind": "lights", "mode": "flash", "rgb": [1, 2, 3], "ms": 80}, t + i * 0.5 + 0.03 + i * 0.001)
    obj = lambda x: {"objects": [{"id": 7, "cls": "cup", "pos": [x, 0.5], "size": [0.1, 0.1], "conf": 1}]}  # noqa: E731
    lat.on("vision.state", obj(0.2), 200.0)
    lat.on("vision.state", obj(0.4), 200.1)                       # moved
    lat.on("world.objects", obj(0.2), 200.2)                      # stale map
    lat.on("world.objects", obj(0.4), 200.35)                     # updated: 250 ms
    lat.on("world.current", {"world": {"id": "w-1"}}, 300.0)
    lat.mark_song_change(301.0)
    lat.on("world.transition", {}, 309.0)
    lat.on("world.current", {"world": {"id": "w-2"}}, 310.0)
    print(lat.report())
    s = lat.samples
    assert len(s["beat -> lights"]) == 20 and abs(percentile(s["beat -> lights"], 50) - 0.0395) < 1e-6
    assert len(s["object -> world"]) == 1 and abs(s["object -> world"][0] - 0.25) < 1e-9
    assert s["song -> world"] == [9.0] and s["song -> transition"] == [8.0]
    print("selftest ok")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Measure Genrator latencies (whitepaper §10).")
    p.add_argument("--hub", help="hub URL (default 127.0.0.1 and HUB_PORT from shared/config.json)")
    p.add_argument("--seconds", type=float, default=60.0)
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.hub:
        from server.common.config import load_config
        c = load_config()
        args.hub = f"{'wss' if c.get('TLS_CERT') and c.get('TLS_KEY') else 'ws'}://127.0.0.1:{c['HUB_PORT']}/hub"
    lat = Latency()
    try:
        asyncio.run(listen(args.hub, args.seconds, lat))
    except KeyboardInterrupt:
        pass
    print()
    print(lat.report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
