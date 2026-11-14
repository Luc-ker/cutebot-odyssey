"""World composition scheduler (T74, contracts C3 and C7)."""

from __future__ import annotations

import asyncio
import copy
import inspect
import logging
import time
import urllib.request
from typing import Any

from server.audio.change import ChangeDetector
from server.audio.clips import ClipStore
from server.audio.signature import distance, signature
from server.common.config import load_config
from server.gemini.client import compose_world
from server.gemini.guard import guard_world
from server.world.fallback_roles import load_vocab, pick_role
from server.world.fallback_worlds import load_fallback_worlds
from server.world.memory import RoleMemory
from server.world.registry import ObjectRegistry
from server.world.worlds import WorldRegistry

log = logging.getLogger(__name__)
MIN_CHANGE_INTERVAL_S = 4.0
CURRENT_REPUBLISH_S = 5.0
LOOP_SLEEP_S = 0.25


def _object_dict(obj: Any) -> dict:
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return vars(obj)
    return {}


async def _fetch_snapshot(config: dict) -> bytes:
    """The robot's current view from the vision service (people blurred)."""
    url = f"http://{config.get('VISION_HOST', '127.0.0.1')}:{int(config.get('VISION_HTTP_PORT', 8080))}/snapshot.jpg"

    def fetch():
        with urllib.request.urlopen(url, timeout=4) as response:
            return response.read()

    return await asyncio.to_thread(fetch)


class WorldScheduler:
    """Injectable world loop; production wiring is exposed by :func:`run`."""

    def __init__(self, hub, config: dict, *, audio_input=None, clip_store=None, change_detector=None,
                 world_registry=None, object_registry=None, role_memory=None, fallbacks=None,
                 compose=compose_world, guard=guard_world, signature_fn=signature,
                 distance_fn=distance, snapshot_fetcher=_fetch_snapshot, vocab=None, clock=time.time):
        self.hub = hub
        self.config = config
        self.audio_input = audio_input
        self.clip_store = clip_store
        self.change_detector = change_detector
        self.world_registry = world_registry or WorldRegistry(config)
        self.object_registry = object_registry or ObjectRegistry(config)
        self.role_memory = role_memory or RoleMemory()
        self.compose = compose
        self.guard = guard
        self.signature_fn = signature_fn
        self.distance_fn = distance_fn
        self.snapshot_fetcher = snapshot_fetcher
        self.vocab = vocab if vocab is not None else load_vocab()
        self.clock = clock
        self.current: dict | None = None
        self.previous_id: str | None = None
        self.silent = True
        self.change_pending = False
        self.in_flight = False
        self.last_call = float("-inf")
        self.last_publish = float("-inf")
        self._health_task: asyncio.Task | None = None
        for fallback in fallbacks if fallbacks is not None else load_fallback_worlds():
            self.world_registry.add(copy.deepcopy(fallback), fallback=True)

    async def start(self) -> None:
        """Adopt the kingdom fallback immediately so the demo always has a world."""
        fallback = self.world_registry.get_by_name("kingdom")
        if fallback is None:
            raise RuntimeError("The required kingdom fallback world is missing")
        await self._adopt(fallback, returning=False)

    def on_audio_features(self, data: dict) -> None:
        self.silent = bool(data.get("silent", False))

    def on_vision_state(self, data: dict, now: float | None = None) -> None:
        self.object_registry.update(data, self.clock() if now is None else now)

    def mark_changed(self) -> None:
        self.change_pending = True

    async def tick(self, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        if self.current and now - self.last_publish >= CURRENT_REPUBLISH_S:
            await self._publish_current()
            self.last_publish = now
        due_interval = now - self.last_call >= float(self.config.get("GEMINI_INTERVAL_S", 8.0))
        due_change = self.change_pending and now - self.last_call >= MIN_CHANGE_INTERVAL_S
        if (due_interval or due_change) and not self.silent and not self.in_flight:
            self.change_pending = False
            await self.request_world(now)

    async def request_world(self, now: float | None = None) -> bool:
        now = self.clock() if now is None else now
        if self.silent or self.in_flight or now - self.last_call < MIN_CHANGE_INTERVAL_S:
            self.change_pending = True
            return False
        self.in_flight = True
        self.last_call = now
        try:
            seconds = float(self.config.get("CLIP_SECONDS", 7.0))
            audio_wav = self.clip_store.get_clip(seconds)
            if not audio_wav:
                return False
            sample_window = self.audio_input.last(seconds)
            music_signature = self.signature_fn(sample_window, self.audio_input.rate)
            match = self.world_registry.match(music_signature)
            if match and self.current and match.get("id") != self.current.get("id"):
                await self._adopt(match, returning=True)
                return True

            image_jpeg = self.snapshot_fetcher(self.config)
            if inspect.isawaitable(image_jpeg):
                image_jpeg = await image_jpeg
            objects = [_object_dict(obj) for obj in self.object_registry.all()]
            # A bundled fallback has never been composed from this session's music.
            # Its example signature/setting must not suppress the first real result.
            current_is_fallback = bool(self.current and self.world_registry.is_fallback(self.current.get("id")))
            raw = await self.compose(audio_wav, image_jpeg, objects,
                                     None if current_is_fallback else self.current)
            guarded = self.guard(raw, objects, self.vocab)
            if inspect.isawaitable(guarded):
                guarded = await guarded
            if guarded is None:
                raise ValueError("Gemini response failed world validation")
            guarded["music_signature"] = music_signature
            if self.current and not current_is_fallback:
                current_signature = self.current.get("music_signature")
                setting = (guarded.get("world") or {}).get("setting", "").casefold()
                current_setting = (self.current.get("world") or {}).get("setting", "").casefold()
                if (not current_signature or self.distance_fn(music_signature, current_signature) <=
                        float(self.config.get("WORLD_CHANGE_THRESHOLD", 0.35)) or setting == current_setting):
                    return False
            guarded.pop("id", None)
            world = self.world_registry.add(guarded)
            await self._adopt(world, returning=False)
            await self._publish_health(True, "world composition succeeded")
            return True
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("world composition failed; keeping current world")
            await self._publish_health(False, str(exc))
            return False
        finally:
            self.in_flight = False

    async def select(self, name: str) -> bool:
        world = self.world_registry.get_by_name(name)
        if world is None or not self.world_registry.is_fallback(world.get("id")):
            return False
        await self._adopt(world, returning=False)
        return True

    async def reset(self) -> None:
        self.current = None
        self.previous_id = None
        self.last_call = float("-inf")
        self.last_publish = float("-inf")
        self.change_pending = False
        self.silent = True
        if self.audio_input and hasattr(self.audio_input, "clear"):
            self.audio_input.clear()
        if self.change_detector:
            self.change_detector.reset()

    async def _adopt(self, world: dict, returning: bool) -> None:
        adopted = copy.deepcopy(world)
        world_id = adopted.get("id")
        if not world_id:
            adopted = self.world_registry.add(adopted)
            world_id = adopted["id"]
        source_roles = {int(role["object_id"]): role for role in adopted.get("roles", [])
                        if isinstance(role, dict) and "object_id" in role}
        assigned = []
        used = []
        for item in self.object_registry.all():
            obj = _object_dict(item)
            object_id = int(obj["id"])
            role = self.role_memory.get(world_id, object_id) or source_roles.get(object_id)
            if role is None:
                role = pick_role(adopted, obj.get("cls", "object"), used, obj_id=object_id, vocab=self.vocab)
            stored = self.role_memory.set(world_id, object_id, role)
            assigned.append({"object_id": object_id, **stored})
            used.append(stored["role"])
        adopted["roles"] = assigned
        old_id = self.current.get("id") if self.current else None
        self.previous_id = old_id
        self.current = adopted
        await self._publish_current()
        await self.hub.pub("world.event", {"kind": "world_changed", "world_id": world_id,
                                             "returning": bool(returning)})
        self.last_publish = self.clock()

    async def _publish_current(self) -> None:
        if self.current:
            await self.hub.pub("world.current", {"world": self.current, "previous_id": self.previous_id})

    async def _publish_health(self, ok: bool, detail: str) -> None:
        await self.hub.pub("system.health", {"service": "gemini", "ok": ok, "detail": detail[:160]})
        if not ok:
            if self._health_task:
                self._health_task.cancel()
            self._health_task = asyncio.create_task(self._restore_health())

    async def _restore_health(self) -> None:
        await asyncio.sleep(2.0)
        await self.hub.pub("system.health", {"service": "gemini", "ok": True, "detail": "ready"})


async def run(hub, config: dict | None = None) -> None:
    """Wire audio, vision and fallback selection into the hub world loop."""
    from server.audio.capture import AudioInput

    config = config or load_config()
    music_enabled = config.get("MUSIC_ENABLED", True)
    audio = AudioInput(config) if music_enabled else None
    scheduler = WorldScheduler(hub, config, audio_input=audio,
                               clip_store=ClipStore(audio) if audio else None,
                               change_detector=ChangeDetector(audio.rate) if audio else None)
    await scheduler.start()

    async def with_data(env: dict, fn):
        fn(env.get("data") or {})

    async def on_world_select(env: dict):
        await scheduler.select(str((env.get("data") or {}).get("name", "")))

    async def on_reset(_env: dict):
        await scheduler.reset()
        if not music_enabled:
            await scheduler.start()

    if music_enabled:
        hub.sub("audio.features", lambda env: with_data(env, scheduler.on_audio_features))
    hub.sub("vision.state", lambda env: with_data(env, scheduler.on_vision_state))
    hub.sub("world.select", on_world_select)
    hub.sub("system.reset", on_reset)

    loop = asyncio.get_running_loop()

    def on_audio(samples, ts):
        if scheduler.change_detector.update(samples, ts):
            loop.call_soon_threadsafe(scheduler.mark_changed)

    if audio:
        audio.on_block(on_audio)
    try:
        try:
            if audio:
                audio.start()
        except Exception as exc:
            log.exception("audio capture unavailable; fallback world remains active")
            await scheduler._publish_health(False, str(exc))
        while True:
            await scheduler.tick()
            await asyncio.sleep(LOOP_SLEEP_S)
    finally:
        if audio:
            audio.stop()
