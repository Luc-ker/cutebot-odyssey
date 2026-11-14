"""T104 — wire every brain module to the hub (contract C7).

    shared = build_shared(config, groups)           # AudioInput, ObjectRegistry, RoleMemory, WorldRegistry, ClipStore
    brain = Brain(hub, config, select_modules(only={"audio", "world"}), shared)
    await brain.run()                                # runs until cancelled

Each module listed in ``MODULES`` exposes ``async def run(hub, config, ...)``. Some loop forever, some
subscribe and return at once ("attached"); both are fine. Modules are imported defensively:

- missing module (not merged yet, or a dependency such as ``sounddevice`` is absent) → logged, reported as
  ``system.health {service: "brain.<name>", ok: false, detail: "missing: ..."}``, never retried;
- ``run`` raises → reported not ok, its subscriptions are removed, and it is restarted after
  ``RESTART_DELAY_S`` (at most ``MAX_RESTARTS`` times), while every other module keeps running.

Shared objects are passed only to modules whose ``run`` has a parameter for them (by name, see
``SHARED_PARAMS``), so a module that does not take one simply makes its own.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("brain")

RESTART_DELAY_S = 2.0
MAX_RESTARTS = 5
HEALTH_INTERVAL_S = 2.0


@dataclass(frozen=True)
class ModuleSpec:
    name: str            # short name, used in health ("brain.<name>") and logs
    path: str            # import path of the module that has run()
    group: str           # for --only / --skip
    optional: bool = False                                  # stretch goal: missing is not an error
    params: dict[str, str] = field(default_factory=dict)    # run() param name -> shared key, overrides SHARED_PARAMS


# Default mapping from a run() parameter name to the shared object it receives.
SHARED_PARAMS = {
    "audio": "audio", "audio_input": "audio",
    "memory": "memory", "role_memory": "memory",
    "object_registry": "objects", "objects_registry": "objects",
    "world_registry": "worlds", "worlds": "worlds",
    "clips": "clips", "clip_store": "clips",
}

MODULES: list[ModuleSpec] = [
    # rhythm loop (fast, local)
    ModuleSpec("beat", "server.audio.beat", "audio"),
    ModuleSpec("features", "server.audio.features", "audio"),
    ModuleSpec("light_director", "server.bridge.light_director", "lights"),
    # world memory and game logic
    ModuleSpec("registry", "server.world.registry", "world", params={"registry": "objects"}),
    ModuleSpec("memory", "server.world.memory", "world"),
    ModuleSpec("worlds", "server.world.worlds", "world", params={"registry": "worlds"}),
    ModuleSpec("arrivals", "server.world.arrivals", "world", params={"registry": "objects"}),
    ModuleSpec("objects_publisher", "server.world.objects_publisher", "world", params={"registry": "objects"}),
    ModuleSpec("robot_state", "server.world.robot_state", "world"),
    ModuleSpec("proximity", "server.world.proximity", "world"),
    ModuleSpec("threat_reaction", "server.world.threat_reaction", "world"),
    ModuleSpec("friendly_reaction", "server.world.friendly_reaction", "world"),
    ModuleSpec("blocked", "server.world.blocked", "world"),
    ModuleSpec("giants", "server.world.giants", "world"),
    ModuleSpec("reset", "server.world.reset", "world"),
    ModuleSpec("transitions", "server.world.transitions", "world"),
    # world loop (Gemini)
    ModuleSpec("scheduler", "server.gemini.scheduler", "gemini", params={"registry": "worlds"}),
    ModuleSpec("talk", "server.gemini.talk", "gemini", optional=True),
    # robot's-eye prompt
    ModuleSpec("prompt_composer", "server.world.prompt_composer", "video"),
    ModuleSpec("prompt_blend", "server.world.prompt_blend", "video"),
    # narration and buttons
    ModuleSpec("narration_queue", "server.narration.queue", "narration"),
    ModuleSpec("narration_triggers", "server.narration.triggers", "narration"),
    ModuleSpec("shout", "server.narration.shout", "narration"),
    ModuleSpec("buttons", "server.narration.buttons", "narration"),
    # USB micro:bit; the launcher runs this group in its own process (it blocks on serial reads)
    ModuleSpec("serial_bridge", "server.bridge.serial_bridge", "bridge"),
]

GROUPS = sorted({m.group for m in MODULES})


def select_modules(only: set[str] | None = None, skip: set[str] | None = None,
                   modules: list[ModuleSpec] | None = None) -> list[ModuleSpec]:
    """Filter by group or module name. ``only`` empty/None = everything."""
    modules = MODULES if modules is None else modules
    out = []
    for m in modules:
        keys = {m.group, m.name}
        if only and not keys & only:
            continue
        if skip and keys & skip:
            continue
        out.append(m)
    return out


# ------------------------------------------------------------------------------------- shared objects

def _try(name: str, make: Callable[[], Any]) -> Any:
    try:
        return make()
    except Exception as exc:  # ImportError, missing audio device, ...
        log.warning("shared %s unavailable: %s", name, exc)
        return None


def build_shared(config: dict, modules: list[ModuleSpec]) -> dict[str, Any]:
    """Create the objects several modules share. Audio is only opened when an audio-hungry module runs."""
    groups = {m.group for m in modules}
    shared: dict[str, Any] = {}

    def objects():
        from server.world.registry import ObjectRegistry
        return ObjectRegistry(config)

    def memory():
        from server.world.memory import RoleMemory
        return RoleMemory()

    def worlds():
        from server.world.worlds import WorldRegistry
        return WorldRegistry(config)

    shared["objects"] = _try("objects", objects)
    shared["memory"] = _try("memory", memory)
    shared["worlds"] = _try("worlds", worlds)

    if groups & {"audio", "gemini"}:
        def audio():
            from server.audio.capture import AudioInput
            return AudioInput(config).start()

        shared["audio"] = _try("audio", audio)
        if shared["audio"] is not None:
            def clips():
                from server.audio.clips import ClipStore
                return ClipStore(shared["audio"])

            shared["clips"] = _try("clips", clips)
    return {k: v for k, v in shared.items() if v is not None}


def kwargs_for(run: Callable, spec: ModuleSpec, shared: dict[str, Any]) -> dict[str, Any]:
    """Shared objects this ``run`` asks for, by parameter name."""
    try:
        params = inspect.signature(run).parameters
    except (TypeError, ValueError):
        return {}
    out = {}
    for pname in params:
        key = spec.params.get(pname) or SHARED_PARAMS.get(pname)
        if key and key in shared:
            out[pname] = shared[key]
    return out


# ------------------------------------------------------------------------------------- supervision

class ScopedHub:
    """Hub proxy that remembers a module's subscriptions so they can be removed before a restart."""

    def __init__(self, hub):
        self._hub = hub
        self._offs: list[Callable[[], None]] = []

    def sub(self, pattern, callback):
        off = self._hub.sub(pattern, callback)
        if callable(off):
            self._offs.append(off)
        return off

    async def pub(self, topic, data=None):
        return await self._hub.pub(topic, data)

    def drop_subscriptions(self) -> None:
        for off in self._offs:
            try:
                off()
            except Exception:
                pass
        self._offs.clear()

    def __getattr__(self, item):
        return getattr(self._hub, item)


@dataclass
class ModuleState:
    spec: ModuleSpec
    ok: bool = False
    detail: str = "starting"
    restarts: int = 0
    since: float = field(default_factory=time.time)

    def set(self, ok: bool, detail: str) -> None:
        self.ok, self.detail, self.since = ok, detail, time.time()


class Brain:
    def __init__(self, hub, config: dict, modules: list[ModuleSpec], shared: dict[str, Any] | None = None,
                 restart_delay: float = RESTART_DELAY_S, max_restarts: int = MAX_RESTARTS,
                 health_interval: float = HEALTH_INTERVAL_S, importer: Callable[[str], Any] | None = None):
        self.hub = hub
        self.config = config
        self.shared = shared or {}
        self.restart_delay = restart_delay
        self.max_restarts = max_restarts
        self.health_interval = health_interval
        self.importer = importer or importlib.import_module
        self.states = {m.name: ModuleState(m) for m in modules}
        self.tasks: dict[str, asyncio.Task] = {}

    async def _health(self, st: ModuleState) -> None:
        if st.spec.optional and st.detail.startswith("missing"):
            return
        try:
            await self.hub.pub("system.health", {"service": f"brain.{st.spec.name}", "ok": st.ok,
                                                 "detail": st.detail})
        except Exception:
            log.debug("health publish failed", exc_info=True)

    async def supervise(self, spec: ModuleSpec) -> None:
        st = self.states[spec.name]
        try:
            mod = self.importer(spec.path)
            run = getattr(mod, "run")
        except Exception as exc:
            level = log.info if spec.optional else log.error
            level("module %s (%s) missing: %s", spec.name, spec.path, exc)
            st.set(False, f"missing: {type(exc).__name__}: {exc}")
            await self._health(st)
            return
        scoped = ScopedHub(self.hub)
        while True:
            st.set(True, "running" if st.restarts == 0 else f"running (restart {st.restarts})")
            try:
                await run(scoped, self.config, **kwargs_for(run, spec, self.shared))
                st.set(True, "attached" if st.restarts == 0 else f"attached (restart {st.restarts})")
                await self._health(st)
                return  # subscribed and returned: it lives on in its callbacks
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("module %s crashed", spec.name)
                scoped.drop_subscriptions()
                if st.restarts >= self.max_restarts:
                    st.set(False, f"gave up after {st.restarts} restarts: {type(exc).__name__}: {exc}")
                    await self._health(st)
                    return
                st.restarts += 1
                st.set(False, f"crashed: {type(exc).__name__}: {exc}; restarting")
                await self._health(st)
                await asyncio.sleep(self.restart_delay)

    async def health_loop(self) -> None:
        while True:
            counted = [s for s in self.states.values()
                       if not (s.spec.optional and s.detail.startswith("missing"))]
            for st in counted:
                await self._health(st)
            await self.hub.pub("system.health", {
                "service": "brain", "ok": True,
                "detail": f"{sum(s.ok for s in counted)}/{len(counted)} modules ok"})
            await asyncio.sleep(self.health_interval)

    def start(self) -> None:
        for name, st in self.states.items():
            self.tasks[name] = asyncio.create_task(self.supervise(st.spec), name=f"brain-{name}")
        self.tasks["_health"] = asyncio.create_task(self.health_loop(), name="brain-health")

    async def run(self) -> None:
        self.start()
        try:
            await asyncio.Event().wait()
        finally:
            await self.stop()

    async def stop(self) -> None:
        for t in self.tasks.values():
            t.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        audio = self.shared.get("audio")
        stop = getattr(audio, "stop", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                pass
