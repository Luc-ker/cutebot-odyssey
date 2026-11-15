"""World composition scheduler (T74, contracts C3 and C7)."""

from __future__ import annotations

import asyncio
import collections
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
from server.world import stable
from server.world.fallback_worlds import load_fallback_worlds
from server.world.memory import RoleMemory
from server.world.registry import ObjectRegistry
from server.world.worlds import WorldRegistry

log = logging.getLogger(__name__)
MIN_CHANGE_INTERVAL_S = 4.0
# After a detected song change, wait until most of the clip sent to Gemini is the new song: a clip that
# is half the old song gets a signature (and a world) that looks like the old one.
SONG_SETTLE_S = 5.0
IDLE_RETURN_S = 10.0  # this long without music (show running, listening on) brings back the Kingdom
RECENT_FALLBACKS = 3  # built-in scenes used as a forced change are not reused until 3 others have been
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
        # Stable Kingdom mode: arrivals (after settling) is the only role assigner, so adopting the
        # world never hands unsettled detections a role of their own.
        self.stable = stable.enabled(config)
        self.current: dict | None = None
        self.previous_id: str | None = None
        self.silent = True
        self.silent_since: float | None = None  # when the current stretch of silence began
        self.change_pending = False
        self.changed_at = float("-inf")
        # Show controls (eye page buttons, ``show.set``): a stopped show or "listen" off never changes
        # the world from music. Listening needs a microphone, which stable mode never opens.
        self.recent_fallbacks: collections.deque[str] = collections.deque(maxlen=RECENT_FALLBACKS)
        # The music that produced the current scene (None at start or after a manual select): a timed
        # check holds the scene while the music stays close to it.
        self.music_for_current: dict | None = None
        self.running = True
        self.can_listen = audio_input is not None
        self.listening = self.can_listen
        self.in_flight = False
        self.last_call = float("-inf")
        self.last_publish = float("-inf")
        self._health_task: asyncio.Task | None = None
        for fallback in fallbacks if fallbacks is not None else load_fallback_worlds():
            self.world_registry.add(copy.deepcopy(fallback), fallback=True)

    async def start(self) -> None:
        """Adopt the starting fallback immediately so the demo always has a world.

        That is Kingdom, or the ``STABLE_WORLD`` world when stable mode locks the run to it."""
        key = stable.world_key(self.config) if self.stable else stable.DEFAULT_WORLD
        fallback = self.world_registry.get_by_name(key)
        if fallback is None:
            raise RuntimeError(f"The required {key} fallback world is missing")
        await self._adopt(fallback, returning=False)

    def on_audio_features(self, data: dict) -> None:
        silent = bool(data.get("silent", False))
        if silent and not self.silent:
            self.silent_since = self.clock()
        elif not silent:
            self.silent_since = None
        self.silent = silent

    def on_vision_state(self, data: dict, now: float | None = None) -> None:
        self.object_registry.update(data, self.clock() if now is None else now)

    def show_state(self) -> dict:
        return {"running": self.running, "listening": self.listening, "can_listen": self.can_listen}

    async def set_show(self, data: dict) -> None:
        """``show.set {running?, listening?}`` from an eye page button; answers with ``show.state``."""
        if isinstance(data.get("running"), bool):
            self.running = data["running"]
        if isinstance(data.get("listening"), bool):
            self.listening = data["listening"] and self.can_listen
        if not (self.running and self.listening):
            self.change_pending = False  # a song heard while paused is not a reason to change later
        await self.hub.pub("show.state", self.show_state())

    def mark_changed(self) -> None:
        """The change detector heard a new song: compose a new world for it once it has settled."""
        self.change_pending = True
        self.changed_at = self.clock()

    async def tick(self, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        if self.current and now - self.last_publish >= CURRENT_REPUBLISH_S:
            await self._publish_current()
            await self.hub.pub("show.state", self.show_state())  # pages opened mid-run catch up
            self.last_publish = now
        if not (self.running and self.listening):
            self.change_pending = False
            return
        if await self._return_to_kingdom_when_idle(now):
            return
        if self.change_pending and now - self.changed_at < SONG_SETTLE_S:
            return  # a new song just started: let the clip fill with it before asking
        due_interval = now - self.last_call >= float(self.config.get("GEMINI_INTERVAL_S", 8.0))
        due_change = self.change_pending and now - self.last_call >= MIN_CHANGE_INTERVAL_S
        if (due_interval or due_change) and not self.silent and not self.in_flight:
            song_change = self.change_pending
            self.change_pending = False
            await self.request_world(now, song_change=song_change)

    async def request_world(self, now: float | None = None, *, song_change: bool = False) -> bool:
        """Change the world for the music playing now.

        ``song_change`` is True when the change detector heard a new song. A timed check during the same
        song first compares the music with the current world's song on the laptop and, when it is
        close, keeps the world without calling Gemini at all. Past that point the scene always
        changes: to a world this song had before, to Gemini's new world, or, when Gemini fails or comes
        back with the current setting, to one of the 8 built-in scenes.
        """
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
            # Kingdom at start (no music yet) never holds: the first song always changes the scene.
            if not song_change and self.current and self.music_for_current:
                d = self.distance_fn(music_signature, self.music_for_current)
                threshold = float(self.config.get("WORLD_CHANGE_THRESHOLD", 0.35))
                log.info("timed music check: distance %.3f vs threshold %.2f -> %s",
                         d, threshold, "same song, keep" if d <= threshold else "new music, change")
                if d <= threshold:
                    return False  # same song still playing: keep the world quietly, no Gemini call
            elif song_change:
                log.info("song change detected: forcing a new scene")

            # A song heard earlier this session brings its world back without asking Gemini.
            match = self.world_registry.match(music_signature)
            if match and self.current and match.get("id") != self.current.get("id"):
                await self._adopt(match, returning=True)
                self.music_for_current = music_signature
                await self._publish_composing("done", match)
                return True

            # The eye page shows "rendering new scene" from here until done/failed.
            await self._publish_composing("composing")
            try:
                world = await self._compose_new(audio_wav, music_signature)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("world composition failed (%s); switching to a built-in scene", exc)
                await self._publish_health(False, str(exc))
                world = None
            if not (self.running and self.listening):
                return False  # listening was turned off (or the show stopped) while Gemini worked
            if world is None:
                world = self._pick_fallback(music_signature)
                if world is None:
                    await self._publish_composing("failed", self.current)
                    return False
                self.recent_fallbacks.append(world["id"])
            await self._adopt(world, returning=False)
            self.music_for_current = music_signature
            await self._publish_composing("done", world)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("music check failed; keeping current world")
            return False
        finally:
            self.in_flight = False

    async def _return_to_kingdom_when_idle(self, now: float) -> bool:
        """No song for IDLE_RETURN_S: the scene goes back to the Kingdom until music starts again."""
        if (not self.silent or self.silent_since is None or self.in_flight
                or now - self.silent_since < float(self.config.get("IDLE_RETURN_S", IDLE_RETURN_S))):
            return False
        kingdom = self.world_registry.get_by_name(stable.DEFAULT_WORLD)
        if kingdom is None or (self.current or {}).get("id") == kingdom.get("id"):
            return False
        log.info("no music for %.0f s: back to the Kingdom", now - self.silent_since)
        await self._adopt(kingdom, returning=False)
        self.music_for_current = None  # the next song always changes it
        await self._publish_composing("done", kingdom)
        return True

    async def _compose_new(self, audio_wav: bytes, music_signature: dict) -> dict | None:
        """Gemini's world for this music, registered, or None when it is no change from now."""
        image_jpeg = self.snapshot_fetcher(self.config)
        if inspect.isawaitable(image_jpeg):
            image_jpeg = await image_jpeg
        objects = [_object_dict(obj) for obj in self.object_registry.all()]
        # No current world goes to Gemini: the compose prompt tells it to keep the current world when
        # unsure, and here the music has already changed.
        raw = await self.compose(audio_wav, image_jpeg, objects, None)
        guarded = self.guard(raw, objects, self.vocab)
        if inspect.isawaitable(guarded):
            guarded = await guarded
        if guarded is None:
            raise ValueError("Gemini response failed world validation")
        setting = (guarded.get("world") or {}).get("setting", "").casefold()
        current_setting = ((self.current or {}).get("world") or {}).get("setting", "").casefold()
        current_is_built_in = bool(self.current and self.world_registry.is_fallback(self.current.get("id")))
        # The starting Kingdom was never made from music, so a Gemini kingdom still counts as new.
        if self.current and not current_is_built_in and setting == current_setting:
            log.info("Gemini returned the current setting (%s); using a built-in scene instead", setting)
            return None
        guarded["music_signature"] = music_signature
        guarded.pop("id", None)
        world = self.world_registry.add(guarded)
        await self._publish_health(True, "world composition succeeded")
        return world

    def _pick_fallback(self, music_signature: dict) -> dict | None:
        """The built-in scene closest to this music, never the current one or a recently used one."""
        current_id = (self.current or {}).get("id")
        built_in = [w for w in self.world_registry.all()
                    if self.world_registry.is_fallback(w.get("id")) and w.get("id") != current_id]
        fresh = [w for w in built_in if w.get("id") not in self.recent_fallbacks] or built_in
        if not fresh:
            return None

        def closeness(w: dict) -> float:
            sig = w.get("music_signature")
            try:
                return self.distance_fn(music_signature, sig) if sig else 1.0
            except Exception:
                return 1.0
        return min(fresh, key=closeness)

    async def select(self, name: str) -> bool:
        world = self.world_registry.get_by_name(name)
        if world is None or not self.world_registry.is_fallback(world.get("id")):
            return False
        await self._adopt(world, returning=False)
        self.music_for_current = None  # picked by hand: the next music changes it
        return True

    async def reset(self) -> None:
        self.current = None
        self.silent_since = None
        self.music_for_current = None
        self.recent_fallbacks.clear()
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
        for item in ([] if self.stable else self.object_registry.all()):
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

    async def _publish_composing(self, state: str, world: dict | None = None) -> None:
        """``world.composing`` (C3): music-driven composition progress, for the eye page HUD."""
        data = {"state": state}
        name = ((world or {}).get("world") or {}).get("name")
        if name and state != "composing":
            data["name"] = name
        await self.hub.pub("world.composing", data)

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
    stable_kingdom = stable.enabled(config)
    # Stable Kingdom mode never composes music worlds, so it never opens the microphone either.
    music_enabled = config.get("MUSIC_ENABLED", True) and not stable_kingdom
    audio = AudioInput(config) if music_enabled else None
    scheduler = WorldScheduler(hub, config, audio_input=audio,
                               clip_store=ClipStore(audio) if audio else None,
                               change_detector=ChangeDetector(audio.rate) if audio else None)
    await scheduler.start()

    async def with_data(env: dict, fn):
        fn(env.get("data") or {})

    async def on_world_select(env: dict):
        if stable_kingdom:
            return  # the stable world stays locked; no world switches mid-demo
        await scheduler.select(str((env.get("data") or {}).get("name", "")))

    async def on_reset(_env: dict):
        await scheduler.reset()
        if not music_enabled:
            await scheduler.start()

    if music_enabled:
        hub.sub("audio.features", lambda env: with_data(env, scheduler.on_audio_features))
    hub.sub("vision.state", lambda env: with_data(env, scheduler.on_vision_state))
    hub.sub("world.select", on_world_select)
    hub.sub("show.set", lambda env: scheduler.set_show(env.get("data") or {}))
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
