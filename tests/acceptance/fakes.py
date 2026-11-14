"""Shared fakes and harness for the end-to-end acceptance tests (T106; T107–T109 import this module).

Everything runs in-process on real code: a real hub (T07) on a free localhost port, real ``HubClient``s (T09),
and the real brain modules, each on its own hub connection as the brain (T104) will run them. Only the
outside world is faked:

* ``FakeAudio``          stands in for ``AudioInput`` (T64): synthetic "songs" with distinct tempo, key and
                          brightness, so the real music signature (T70) can tell them apart.
* ``FakeGemini``         stands in for ``compose_world`` (T71) and ``request_role`` (T76): scripted worlds per
                          song, scripted or forced object roles, and ok / fail / timeout modes.
* ``FakeSnapshotServer`` stands in for the vision service's ``GET /snapshot.jpg`` (T45).
* ``FakeSerialDevice``   stands in for the bridge micro:bit's USB serial port (T22), with unplug / replug.
* ``fake_speaker``       stands in for the sound page (T81): answers every ``narration.speak`` with
                          ``narration.done`` after a short "speaking" delay, so the narration queue keeps moving.

Stand-ins for modules that have not landed yet (each is used only while the real one is missing):

* ``StandInScheduler``   the world scheduler (T74, ``server/gemini/scheduler.py``), coded to the T74 ticket:
                          ``tick()`` matches a returning song first, else asks Gemini (with timeout) and adopts
                          a new world only if the music changed enough; ``world.select`` adopts a fallback world.
                          When T74 lands, point ``make_scheduler`` at it.
* ``fallback_worlds()``  the pre-composed worlds (T75); uses ``server.world.fallback_worlds`` if present.

``Harness`` starts the hub and the modules, publishes test input (including a 10 Hz ``vision.state`` feeder
driven by ``harness.scene``), records every hub message, and collects unhandled exceptions from module tasks,
hub callbacks and the event loop, so tests can assert there were none.
"""

from __future__ import annotations

import asyncio
import copy
import io
import json
import logging
import math
import secrets
import sys
import threading
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from server.audio.signature import distance as sig_distance, signature  # noqa: E402
from server.common.config import load_config  # noqa: E402
from server.common.hub_client import HubClient  # noqa: E402
from server.hub.server import HubServer  # noqa: E402
from server.world.memory import RoleMemory  # noqa: E402
from server.world.registry import ObjectRegistry  # noqa: E402
from server.world.worlds import WorldRegistry  # noqa: E402

log = logging.getLogger("acceptance")

# ---------------------------------------------------------------------------------------------- config


def test_config(**overrides) -> dict:
    """The shared config with test overrides (e.g. a short grace period)."""
    cfg = dict(load_config())
    cfg.update(overrides)
    return cfg


# ---------------------------------------------------------------------------------------------- audio

FAKE_RATE = 22050


@dataclass(frozen=True)
class Song:
    bpm: float
    freqs: tuple       # chord tones (Hz): sets the key / chroma
    bright: float      # 0..1, amount of bright noise: sets brightness


SONGS = {
    "sea_shanty": Song(90, (130.8, 164.8, 196.0), 0.0),      # C major, slow, dark
    "heavy_metal": Song(150, (740.0, 932.3, 1108.7), 1.0),   # F# major high, fast, bright
    "synthwave": Song(120, (220.0, 277.2, 329.6), 0.4),      # A major, mid
}


def render(song: Song, seconds: float, offset: float = 0.0, rate: int = FAKE_RATE) -> np.ndarray:
    t = np.arange(int(seconds * rate)) / rate + offset
    period = 60.0 / song.bpm
    env = np.exp(-((t % period) / period) * 8)
    tone = sum(np.sin(2 * np.pi * f * t) for f in song.freqs) / len(song.freqs)
    noise = np.random.default_rng(int(song.bpm)).standard_normal(t.size)
    noise = np.diff(np.concatenate([[0.0], noise]))  # tilt it bright
    x = 0.5 * tone * (0.3 + 0.7 * env) + song.bright * 0.25 * noise * env
    return (0.5 * x).astype(np.float32)


def to_wav(samples: np.ndarray, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


class FakeAudio:
    """``AudioInput``-shaped (T64): ``rate``, ``last(seconds)``, ``on_block``, ``start``. ``play(name)`` switches
    song; each play starts at a new point in the song, as a real replay would."""

    def __init__(self, rate: int = FAKE_RATE):
        self.rate = rate
        self.song: str | None = None
        self._offset = 0.0

    def start(self):
        return self

    def on_block(self, _cb):
        pass

    def play(self, name: str | None):
        if name is not None and name not in SONGS:
            raise KeyError(name)
        self.song = name
        self._offset += 13.37

    def stop(self):
        self.song = None

    @property
    def silent(self) -> bool:
        return self.song is None

    def last(self, seconds: float) -> np.ndarray:
        if self.song is None:
            return np.zeros(int(seconds * self.rate), dtype=np.float32)
        return render(SONGS[self.song], seconds, self._offset, self.rate)

    def clip_wav(self, seconds: float = 7.0) -> bytes | None:
        return None if self.song is None else to_wav(self.last(seconds), self.rate)


# ---------------------------------------------------------------------------------------------- gemini


class FakeGemini:
    """Scripted Gemini. ``worlds[song]`` is the raw world (C4 without id/signature) composed for that song.

    ``mode``: "ok" | "fail" (raises) | "timeout" (never answers). ``forced_role`` makes every
    ``request_role`` return that role. Otherwise roles are per object class, and every answer's name carries a
    call counter, so a system that forgets a role and asks again visibly gets a different one.
    """

    ROLE_BY_CLS = {
        "chair": ("castle", "Highkeep", "neutral"),
        "bottle": ("tower", "the Spire", "friendly"),
        "bowl": ("village", "Millbrook", "friendly"),
    }

    def __init__(self, audio: FakeAudio | None = None):
        self.audio = audio
        self.worlds: dict[str, dict] = {}
        self.mode = "ok"
        self.forced_role: dict | None = None
        self.compose_calls = 0
        self.role_calls = 0

    async def _behave(self):
        if self.mode == "fail":
            raise RuntimeError("fake Gemini is down")
        if self.mode == "timeout":
            await asyncio.sleep(3600)

    async def compose_world(self, audio_wav, image_jpeg, objects, current_world) -> dict:
        self.compose_calls += 1
        await self._behave()
        song = self.audio.song if self.audio else None
        if song not in self.worlds:
            raise RuntimeError(f"fake Gemini has no world for song {song!r}")
        return copy.deepcopy(self.worlds[song])

    async def request_role(self, world, obj, image) -> dict | None:
        self.role_calls += 1
        await self._behave()
        if self.forced_role:
            return dict(self.forced_role)
        role, name, behaviour = self.ROLE_BY_CLS.get(obj.get("cls"), ("thing", "the Oddity", "neutral"))
        return {"role": role, "name": f"{name} #{self.role_calls}", "behaviour": behaviour,
                "announce": f"{name} appears."}


def make_world(name: str, setting: str, roles: list[tuple[int, str, str, str]], *, palette=None,
               open_space="open land", narration=None) -> dict:
    """A raw C4 world as Gemini would return it (no id / signature yet)."""
    return {
        "world": {"name": name, "setting": setting, "mood": "bold", "time_of_day": "dusk", "weather": "clear",
                  "palette": palette or ["gold", "green", "ivory"]},
        "roles": [{"object_id": oid, "role": r, "name": n, "behaviour": b} for oid, r, n, b in roles],
        "terrain": {"open_space": open_space, "under_table": "the deep"},
        "restyle_prompt": f"{setting}, painterly",
        "narration": narration or f"You arrive in {name}.",
    }


# ---------------------------------------------------------------------------------------------- fallback worlds


def fallback_worlds() -> list[dict]:
    """The pre-composed worlds (T75), or a two-world stand-in until T75 lands."""
    try:
        from server.world.fallback_worlds import load_fallback_worlds  # T75
        return load_fallback_worlds()
    except ImportError:
        pass
    out = []
    for key, name, setting, space in (("kingdom", "The Amber Realm", "medieval kingdom", "rolling meadows"),
                                      ("ocean", "The Drowned Kingdom", "stormy open ocean", "open sea")):
        w = make_world(name, setting, [], open_space=space)
        w.update({"id": f"w-fb{key[:6]:0<6}", "key": key, "music_signature": {}})
        out.append(w)
    return out


# ---------------------------------------------------------------------------------------------- scheduler stand-in


class StandInScheduler:
    """Coded to the T74 ticket; replace with ``server.gemini.scheduler`` when it lands.

    ``tick()`` is one scheduler step (the real one runs it every ``GEMINI_INTERVAL_S``):
    silent → skip; returning signature → re-adopt that world without Gemini; else Gemini (timeout
    ``GEMINI_TIMEOUT_S``) → adopt if there is no world yet or the music moved more than
    ``WORLD_CHANGE_THRESHOLD`` and the setting differs. Any failure keeps the current world and reports
    ``system.health ok:false``. ``world.select {name}`` adopts a fallback world at once.
    """

    def __init__(self, hub, config, *, audio: FakeAudio, gemini: FakeGemini, worlds: WorldRegistry,
                 memory: RoleMemory, registry: ObjectRegistry):
        self.hub, self.config = hub, config
        self.audio, self.gemini = audio, gemini
        self.worlds, self.memory, self.registry = worlds, memory, registry
        self.timeout_s = float(config.get("GEMINI_TIMEOUT_S", 12.0))
        self.change_threshold = float(config.get("WORLD_CHANGE_THRESHOLD", 0.35))
        self.current: dict | None = None
        for fb in fallback_worlds():
            self.worlds.add(fb, fallback=True)

    def attach(self):
        self.hub.sub("world.select", self._on_select)
        self.hub.sub("system.reset", self._on_reset)
        return self

    async def _on_select(self, env):
        world = self.worlds.get_by_name((env.get("data") or {}).get("name", ""))
        if world:
            await self.adopt(world, returning=False)

    async def _on_reset(self, _env):
        self.current = None

    async def adopt(self, world: dict, returning: bool):
        previous = self.current
        self.current = world
        await self.hub.pub("world.current", {"world": world, "previous_id": (previous or {}).get("id")})
        await self.hub.pub("world.event", {"kind": "world_changed", "world_id": world["id"], "returning": returning})

    async def tick(self) -> str:
        """One step. Returns what happened: "silent" | "returned" | "adopted" | "held" | "failed"."""
        if self.audio.silent:
            return "silent"
        sig = signature(self.audio.last(6.0), self.audio.rate)
        back = self.worlds.match(sig)
        if back and back["id"] != (self.current or {}).get("id"):
            await self.adopt(back, returning=True)
            return "returned"
        try:
            raw = await asyncio.wait_for(
                self.gemini.compose_world(self.audio.clip_wav(), b"", [o.to_dict() for o in self.registry.all()],
                                          self.current),
                timeout=self.timeout_s)
        except Exception as exc:  # timeout, network, bad reply: the world holds
            log.info("compose_world failed: %r", exc)
            await self.hub.pub("system.health", {"service": "gemini", "ok": False, "detail": repr(exc)[:80]})
            return "failed"
        cur_sig = (self.current or {}).get("music_signature") or {}
        same_setting = self.current and (raw.get("world") or {}).get("setting") == (self.current.get("world") or {}).get("setting")
        if self.current and cur_sig and (sig_distance(sig, cur_sig) <= self.change_threshold or same_setting):
            return "held"
        world = dict(raw, id="w-" + secrets.token_hex(4), music_signature=sig)
        self.worlds.add(world)
        for r in world.get("roles") or []:
            self.memory.set(world["id"], int(r["object_id"]), r)
        await self.hub.pub("system.health", {"service": "gemini", "ok": True, "detail": ""})
        await self.adopt(world, returning=False)
        return "adopted"


def make_scheduler(hub, config, **kw):
    return StandInScheduler(hub, config, **kw).attach()


# ---------------------------------------------------------------------------------------------- snapshot server


class FakeSnapshotServer:
    """``GET /snapshot.jpg`` like the vision service (T45): a tiny JPEG-shaped body. Counts requests."""

    BODY = b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"

    def __init__(self):
        self.requests = 0
        self.server = None
        self.port = None

    async def start(self):
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def _handle(self, reader, writer):
        try:
            request = await reader.readuntil(b"\r\n\r\n")
            self.requests += 1
            ok = request.split(b" ")[1].startswith(b"/snapshot.jpg")
            body = self.BODY if ok else b"not found"
            status = b"200 OK" if ok else b"404 Not Found"
            writer.write(b"HTTP/1.1 " + status + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                         + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body)
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()


# ---------------------------------------------------------------------------------------------- serial port


class FakeSerialDevice:
    """The bridge micro:bit on USB. ``open()`` is the bridge's ``open_port``; unplug / replug at will.
    ``written`` keeps every line the laptop wrote (across reconnects); ``feed(line)`` sends one to the laptop."""

    def __init__(self):
        self.plugged = True
        self.written: list[tuple[float, str]] = []
        self.incoming: list[bytes] = []
        self.opens = 0
        self._lock = threading.Lock()

    def open(self):
        if not self.plugged:
            raise OSError("fake micro:bit unplugged")
        self.opens += 1
        return _FakePort(self)

    def feed(self, line: str):
        with self._lock:
            self.incoming.append((line.rstrip("\n") + "\n").encode("ascii"))

    def unplug(self):
        self.plugged = False

    def replug(self):
        self.plugged = True

    def lines(self, prefix: str = "") -> list[str]:
        return [ln for _, ln in self.written if ln.startswith(prefix)]


class _FakePort:
    def __init__(self, dev: FakeSerialDevice):
        self.dev = dev
        self.closed = False

    def _check(self):
        if self.closed or not self.dev.plugged:
            raise OSError("device disconnected")

    def write(self, data: bytes):
        self._check()
        for line in data.decode("ascii").splitlines():
            self.dev.written.append((time.monotonic(), line))
        return len(data)

    def readline(self) -> bytes:  # runs in a worker thread, like pyserial with timeout=0.1
        time.sleep(0.02)
        self._check()
        with self.dev._lock:
            return self.dev.incoming.pop(0) if self.dev.incoming else b""

    def close(self):
        self.closed = True


# ---------------------------------------------------------------------------------------------- speaker


def fake_speaker(speak_s: float = 0.05):
    """A ``run(hub, config)`` for the sound page stand-in: ``narration.speak`` → ``narration.done``."""

    async def run(hub, _config):
        async def on_speak(env):
            await asyncio.sleep(speak_s)
            await hub.pub("narration.done", {"id": (env.get("data") or {}).get("id")})

        hub.sub("narration.speak", on_speak)

    return run


# ---------------------------------------------------------------------------------------------- harness


@dataclass
class Msg:
    topic: str
    data: Any
    t: float  # local monotonic arrival time at the probe


class _ErrorLog(logging.Handler):
    def __init__(self):
        super().__init__(logging.ERROR)
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


@dataclass
class Scene:
    """What the robot's camera currently sees; the harness publishes it as ``vision.state`` at 10 Hz."""
    objects: dict = field(default_factory=dict)   # id -> {id, cls, pos, size, conf}, view units
    giants: list = field(default_factory=list)

    def put(self, obj_id: int, cls: str, pos, size=(0.08, 0.08)):
        self.objects[obj_id] = {"id": obj_id, "cls": cls, "pos": list(pos), "size": list(size), "conf": 0.9}

    def move(self, obj_id: int, pos):
        self.objects[obj_id]["pos"] = list(pos)

    def hide(self, obj_id: int) -> dict:
        return self.objects.pop(obj_id)

    def state(self) -> dict:
        return {"frame_ts": time.time(), "objects": [dict(o) for o in self.objects.values()],
                "giants": [dict(g) for g in self.giants]}


class Harness:
    """``async with Harness(config) as h:`` — a hub on a free port, a fake vision snapshot server
    (``h.snapshot``; the config is pointed at it), a probe recording every message, a 10 Hz vision feeder,
    helpers to start modules and wait for messages, and an error collector."""

    def __init__(self, config: dict | None = None):
        self.config = config if config is not None else test_config()
        self.messages: list[Msg] = []
        self.scene = Scene()
        self.feeding = False
        self.errors: list[str] = []
        self._tasks: list[asyncio.Task] = []
        self._clients: list[HubClient] = []
        self._new_msg = asyncio.Event()

    # -- lifecycle -------------------------------------------------------------------------------------
    async def __aenter__(self):
        loop = asyncio.get_running_loop()
        self._old_handler = loop.get_exception_handler()
        loop.set_exception_handler(lambda _l, ctx: self.errors.append(f"loop: {ctx.get('message')} {ctx.get('exception')!r}"))
        self._errlog = _ErrorLog()
        logging.getLogger().addHandler(self._errlog)

        # the vision service's snapshot endpoint, so nothing ever tries to reach a real one
        self.snapshot = await FakeSnapshotServer().start()
        self.config.update(VISION_HOST="127.0.0.1", VISION_HTTP_PORT=self.snapshot.port)

        self.hub = HubServer()
        await self.hub.start("127.0.0.1", 0)
        self.url = f"ws://127.0.0.1:{self.hub.port}/hub"
        self.probe = await self.client("probe")
        self.probe.sub("*", self._record)
        self.input = await self.client("test")
        self._spawn(self._feeder(), "vision-feeder")
        await asyncio.sleep(0.1)
        return self

    async def __aexit__(self, *exc):
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        for c in self._clients:
            await c.close()
        await self.hub.stop()
        await self.snapshot.stop()
        asyncio.get_running_loop().set_exception_handler(self._old_handler)
        logging.getLogger().removeHandler(self._errlog)
        self.errors += [f"log {r.name}: {r.getMessage()}" for r in self._errlog.records]

    async def client(self, src: str) -> HubClient:
        c = await HubClient.connect(self.url, src, timeout=5)
        self._clients.append(c)
        return c

    def _spawn(self, coro, name: str) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        task.set_name(name)

        def done(t: asyncio.Task):
            if not t.cancelled() and t.exception() is not None:
                self.errors.append(f"task {name}: {t.exception()!r}")

        task.add_done_callback(done)
        self._tasks.append(task)
        return task

    async def start(self, name: str, run: Callable, *args, **kwargs):
        """Start a module's ``run(hub, config, ...)`` on its own hub connection; returns what ``run`` returned
        if it returns at once (most do after subscribing), else None while its loop keeps running."""
        hub = await self.client(name)
        task = self._spawn(run(hub, self.config, *args, **kwargs), name)
        await asyncio.sleep(0.05)
        if task.done() and not task.cancelled() and task.exception() is None:
            return task.result()
        return None

    async def settle(self, seconds: float = 0.25):
        await asyncio.sleep(seconds)

    def assert_no_errors(self):
        errors = self.errors + [f"log {r.name}: {r.getMessage()}" for r in self._errlog.records]
        assert not errors, "unhandled errors:\n" + "\n".join(errors)

    # -- input -----------------------------------------------------------------------------------------
    async def pub(self, topic: str, data: dict):
        await self.input.pub(topic, data)

    async def _feeder(self):
        period = 1.0 / float(self.config.get("VISION_HZ", 10))
        while True:
            if self.feeding:
                await self.input.pub("vision.state", self.scene.state())
            await asyncio.sleep(period)

    # -- output ----------------------------------------------------------------------------------------
    async def _record(self, env):
        self.messages.append(Msg(env["topic"], env.get("data"), time.monotonic()))
        self._new_msg.set()

    def mark(self) -> int:
        """A position in the message log; pass it as ``after`` to only look at newer messages."""
        return len(self.messages)

    def find(self, topic: str, pred: Callable[[Any], bool] | None = None, after: int = 0) -> list[Msg]:
        return [m for m in self.messages[after:] if m.topic == topic and (pred is None or pred(m.data))]

    async def wait_for(self, topic: str, pred: Callable[[Any], bool] | None = None, *, after: int = 0,
                       timeout: float = 3.0) -> Msg:
        deadline = time.monotonic() + timeout
        while True:
            hits = self.find(topic, pred, after)
            if hits:
                return hits[0]
            left = deadline - time.monotonic()
            if left <= 0:
                recent = [f"{m.topic} {json.dumps(m.data)[:120]}" for m in self.messages[-12:]]
                raise AssertionError(f"no {topic} matching within {timeout}s; recent:\n" + "\n".join(recent))
            self._new_msg.clear()
            try:
                await asyncio.wait_for(self._new_msg.wait(), min(left, 0.1))
            except asyncio.TimeoutError:
                pass

    async def latest(self, topic: str, pred: Callable[[Any], bool] | None = None, *, timeout: float = 3.0) -> Any:
        """Data of the newest ``topic`` message published from now on (and matching ``pred``)."""
        return (await self.wait_for(topic, pred, after=self.mark(), timeout=timeout)).data


def object_in(world_objects: dict, obj_id: int) -> dict | None:
    for o in (world_objects or {}).get("objects") or []:
        if o.get("id") == obj_id:
            return o
    return None


def role_of(world_objects: dict, obj_id: int) -> tuple | None:
    o = object_in(world_objects, obj_id)
    return None if o is None or o.get("role") is None else (o["role"], o["name"], o["behaviour"])


def dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])
