"""T50 — New and removed object flow.

When the robot sees an object for the first time, give it a role in the current
world (Gemini first, local picker if Gemini is slow, busy or down), remember it and
announce it with ``world.event object_added``.

In stable Kingdom mode (``STABLE_KINGDOM_ENABLED``) a new object must first stay in view for
``OBJECT_SETTLE_S``; a detection that flickers out sooner is never given a role, announced or sent
to Gemini. Its role then comes from the local picker by detector class alone (no Gemini call), so the
same kind of object always becomes the same thing. An object that comes back into view
is re-identified by vision and keeps its id, so it is not announced again. When the
registry forgets an object (unseen for ``OBJECT_FORGET_S``), publish ``object_removed``.

This module drives the shared ``ObjectRegistry`` (T48): it calls
``registry.update`` for every ``vision.state`` and clears it on ``system.reset``.
If ``vision.state`` stops arriving altogether (the vision service or the phone is down),
a background check keeps ageing objects so they drop out of view and are eventually
forgotten (whitepaper §7.15).
"""

from __future__ import annotations

import asyncio
import logging
import time
import urllib.request

from server.world import stable
from server.world.fallback_roles import class_role, load_vocab, pick_role as local_pick_role
from server.world.memory import RoleMemory
from server.world.registry import ObjectRegistry

log = logging.getLogger(__name__)

GEMINI_TIMEOUT_S = 4.0
MAX_IN_FLIGHT = 2
SKY_WINDOW_S = 3.0
VISION_IDLE_S = 0.5   # no vision.state for this long (5 missed frames) → age objects ourselves
EXPIRY_TICK_S = 0.25
BEHAVIOURS = ("friendly", "neutral", "threat")


def _announce(role: dict, from_sky: bool) -> str:
    name = role.get("name") or role.get("role", "something").replace("_", " ")
    if from_sky:
        return f"From the sky, a giant sets down {name}."
    return f"Ahead, {name} rises from the land."


class Arrivals:
    def __init__(self, hub, config: dict | None = None, *, registry=None, memory=None,
                 request_role=None, pick_role=None, fetch_snapshot=None, vocab=None,
                 clock=time.time, gemini_timeout_s: float = GEMINI_TIMEOUT_S):
        self.hub = hub
        self.config = config or {}
        self.registry = registry if registry is not None else ObjectRegistry(self.config)
        self.memory = memory if memory is not None else RoleMemory()
        self.request_role = request_role
        self.pick_role = pick_role or local_pick_role
        self.fetch_snapshot = fetch_snapshot or self._default_snapshot
        self.vocab = vocab
        self.clock = clock
        self.gemini_timeout_s = gemini_timeout_s
        self.world: dict | None = None
        self.in_flight = 0
        self._last_giant_ts: float | None = None
        self._pending: list[int] = []  # added before any world was known
        self._tasks: set[asyncio.Task] = set()
        self._last_vision_ts: float | None = None
        self._expiry_task: asyncio.Task | None = None
        self.stable = stable.enabled(self.config)
        self.settle_s = stable.settle_s(self.config) if self.stable else 0.0
        self._settling: dict[int, float | None] = {}  # obj id -> start of its current continuous view

    # -- hub wiring --------------------------------------------------------
    def attach(self):
        self.hub.sub("vision.state", self._on_vision)
        self.hub.sub("world.current", self._on_world)
        self.hub.sub("system.reset", self._on_reset)
        return self

    async def _on_vision(self, env):
        self.handle_vision(env.get("data") or {}, self.clock())

    async def _on_world(self, env):
        world = (env.get("data") or {}).get("world")
        if world:
            self.set_world(world)

    async def _on_reset(self, _env):
        self.reset()

    # -- logic -------------------------------------------------------------
    def reset(self):
        for t in list(self._tasks):
            t.cancel()
        self._tasks.clear()
        self.registry.clear()
        self.world = None
        self._pending.clear()
        self._settling.clear()
        self._last_giant_ts = None
        self._last_vision_ts = None
        self.in_flight = 0

    def set_world(self, world: dict):
        changed = not self.world or self.world.get("id") != world.get("id")
        self.world = world
        if changed and self._pending:
            pending, self._pending = self._pending, []
            for obj_id in pending:
                if self.registry.get(obj_id):
                    self._admit(obj_id, from_sky=False, now=self.clock())

    def handle_vision(self, data: dict, now: float):
        """Feed one vision.state; schedules role assignment for new objects."""
        self._last_vision_ts = now
        if data.get("giants"):
            self._last_giant_ts = now
        diff = self.registry.update(data, now)
        from_sky = self._last_giant_ts is not None and now - self._last_giant_ts <= SKY_WINDOW_S
        for obj_id in diff.added:
            if self.world is None:
                self._pending.append(obj_id)
            else:
                self._admit(obj_id, from_sky, now)
        self._removed(diff.removed)
        self._check_settled(now, from_sky)
        return diff

    def _admit(self, obj_id: int, from_sky: bool, now: float) -> None:
        """A new object: assign now, or (stable mode) once it has settled in view."""
        if self.settle_s > 0:
            self._settling[obj_id] = now
            self._check_settled(now, from_sky)
        else:
            self._spawn(self.assign(obj_id, from_sky))

    def _check_settled(self, now: float, from_sky: bool) -> None:
        for obj_id, since in list(self._settling.items()):
            obj = self.registry.get(obj_id)
            if obj is None:
                del self._settling[obj_id]
            elif not obj.visible:
                self._settling[obj_id] = None  # flickered out: the clock starts again
            elif since is None:
                self._settling[obj_id] = now
            elif now - since >= self.settle_s and self.world is not None:
                del self._settling[obj_id]
                self._spawn(self.assign(obj_id, from_sky))

    def _removed(self, removed) -> None:
        for obj_id in removed:
            if obj_id in self._pending:
                self._pending.remove(obj_id)
            if self._settling.pop(obj_id, "announced") != "announced":
                continue  # never settled, so never announced: nothing to take back
            self._spawn(self._publish("world.event", {"kind": "object_removed", "id": obj_id}))

    def expire_if_idle(self, now: float) -> list[int]:
        """When vision.state has been silent for VISION_IDLE_S, drop objects past their grace period
        (as a frame with nothing in it would) and publish ``object_removed``. Returns the removed ids."""
        if self._last_vision_ts is None or now - self._last_vision_ts < VISION_IDLE_S:
            return []
        diff = self.registry.update(None, now)
        self._removed(diff.removed)
        self._check_settled(now, from_sky=False)
        return diff.removed

    def start_expiry(self):
        """Run :meth:`expire_if_idle` in the background (``run`` does this)."""
        async def loop():
            while True:
                await asyncio.sleep(EXPIRY_TICK_S)
                try:
                    self.expire_if_idle(self.clock())
                except Exception:  # never let the check die; the next tick tries again
                    log.exception("object expiry check failed")

        if self._expiry_task is None or self._expiry_task.done():
            self._expiry_task = asyncio.ensure_future(loop())
        return self._expiry_task

    def _spawn(self, coro):
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _publish(self, topic, data):
        await self.hub.pub(topic, data)

    async def assign(self, obj_id: int, from_sky: bool) -> dict | None:
        world = self.world
        obj = self.registry.get(obj_id)
        if world is None or obj is None:
            return None
        world_id = world.get("id")
        role = self.memory.get(world_id, obj_id)
        announce = None
        if role is None and self.stable:
            # Same class -> same role every time; no Gemini call, so no surprise reinterpretations.
            result = class_role(world, obj.cls,
                                vocab=self.vocab if self.vocab is not None else load_vocab())
            role = self.memory.set(world_id, obj_id, result)
        elif role is None:
            result = None
            if self.request_role is not None and self.in_flight < MAX_IN_FLIGHT:
                result = await self._ask_gemini(world, obj)
            if result is None:
                taken = [r["role"] for r in self.memory.roles_for(world_id).values()]
                result = self.pick_role(world, obj.cls, taken, obj_id=obj_id,
                                        vocab=self.vocab if self.vocab is not None else load_vocab())
            announce = result.get("announce")
            role = self.memory.set(world_id, obj_id, result)
        event = {
            "kind": "object_added", "id": obj_id, "role": role["role"], "name": role["name"],
            "behaviour": role["behaviour"], "announce": announce or _announce(role, from_sky),
            "from_sky": bool(from_sky),
        }
        await self._publish("world.event", event)
        return event

    async def _ask_gemini(self, world, obj) -> dict | None:
        self.in_flight += 1
        try:
            async def call():
                image = await self.fetch_snapshot()
                return await self.request_role(world, obj.to_dict(), image)
            result = await asyncio.wait_for(call(), timeout=self.gemini_timeout_s)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # timeout, network, bad reply
            log.info("object role call failed for %s: %r", obj.id, exc)
            return None
        finally:
            self.in_flight -= 1
        if not isinstance(result, dict) or not result.get("role") or not result.get("name"):
            return None
        if result.get("behaviour") not in BEHAVIOURS:
            result = dict(result, behaviour="neutral")
        return result

    async def _default_snapshot(self) -> bytes | None:
        host = self.config.get("VISION_HOST")
        port = self.config.get("VISION_HTTP_PORT")
        if not host or not port:
            return None
        url = f"http://{host}:{port}/snapshot.jpg"

        def fetch():
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                return resp.read()

        try:
            return await asyncio.to_thread(fetch)
        except Exception:
            return None


def _default_request_role():
    try:
        from server.gemini.object_role import request_role  # T76
        return request_role
    except ImportError:
        return None


async def run(hub, config, *, registry=None, memory=None, request_role=None):
    arrivals = Arrivals(hub, config, registry=registry, memory=memory,
                        request_role=request_role or _default_request_role())
    arrivals.attach()
    arrivals.start_expiry()
    return arrivals
