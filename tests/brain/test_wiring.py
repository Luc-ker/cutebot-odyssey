"""T104 — brain wiring with fake modules: a crashing or missing module never stops the others."""
import asyncio
import types

from server.brain import wiring
from server.brain.wiring import Brain, ModuleSpec, kwargs_for, select_modules


class FakeHub:
    def __init__(self):
        self.subs, self.published = [], []

    def sub(self, pattern, cb):
        entry = (pattern, cb)
        self.subs.append(entry)
        return lambda: entry in self.subs and self.subs.remove(entry)

    async def pub(self, topic, data=None):
        self.published.append((topic, data))
        return True

    def health(self, service):
        return [d for t, d in self.published if t == "system.health" and d["service"] == service]


def fake_importer(mods):
    def importer(path):
        if path not in mods:
            raise ImportError(f"No module named {path!r}")
        return mods[path]
    return importer


def module(run):
    return types.SimpleNamespace(run=run)


def run_brain(brain, seconds):
    async def main():
        brain.start()
        await asyncio.sleep(seconds)
        await brain.stop()
    asyncio.run(main())


def test_crashing_module_does_not_stop_the_others_and_is_reported():
    ticks = []

    async def good(hub, config):
        hub.sub("audio.beat", lambda env: None)
        while True:
            ticks.append(1)
            await asyncio.sleep(0.01)

    async def attached(hub, config):
        hub.sub("system.reset", lambda env: None)

    starts = []

    async def bad(hub, config):
        starts.append(1)
        hub.sub("vision.state", lambda env: None)
        raise RuntimeError("boom")

    mods = {"m.good": module(good), "m.attached": module(attached), "m.bad": module(bad)}
    specs = [ModuleSpec("good", "m.good", "g"), ModuleSpec("attached", "m.attached", "g"),
             ModuleSpec("bad", "m.bad", "g"), ModuleSpec("missing", "m.missing", "g")]
    hub = FakeHub()
    brain = Brain(hub, {}, specs, restart_delay=0.01, max_restarts=3, health_interval=0.02,
                  importer=fake_importer(mods))
    run_brain(brain, 0.3)

    # the good module kept running and the attached one stayed subscribed
    assert len(ticks) > 10
    assert brain.states["good"].ok and brain.states["attached"].ok
    assert ("system.reset" in [p for p, _ in hub.subs])
    # the bad one was restarted max_restarts times, then given up, and its subscriptions were removed
    assert len(starts) == 1 + 3
    assert "vision.state" not in [p for p, _ in hub.subs]
    assert not brain.states["bad"].ok and "gave up" in brain.states["bad"].detail
    assert any(not h["ok"] and "boom" in h["detail"] for h in hub.health("brain.bad"))
    # the missing one is reported, not retried
    assert hub.health("brain.missing") and not hub.health("brain.missing")[-1]["ok"]
    assert "missing" in hub.health("brain.missing")[-1]["detail"]
    # everything healthy is reported ok
    assert hub.health("brain.good")[-1]["ok"]
    assert hub.health("brain")[-1]["detail"] == "2/4 modules ok"


def test_module_that_raises_once_recovers_after_restart():
    calls = []

    async def flaky(hub, config):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("first start fails")
        await asyncio.Event().wait()

    hub = FakeHub()
    brain = Brain(hub, {}, [ModuleSpec("flaky", "m.flaky", "g")], restart_delay=0.01,
                  health_interval=0.02, importer=fake_importer({"m.flaky": module(flaky)}))
    run_brain(brain, 0.1)
    assert len(calls) == 2
    assert brain.states["flaky"].ok and brain.states["flaky"].restarts == 1


def test_optional_missing_module_is_quiet():
    hub = FakeHub()
    brain = Brain(hub, {}, [ModuleSpec("talk", "m.talk", "g", optional=True)], health_interval=0.02,
                  importer=fake_importer({}))
    run_brain(brain, 0.05)
    assert hub.health("brain.talk") == []


def test_shared_objects_are_passed_by_parameter_name():
    seen = {}

    async def wants(hub, config, *, registry=None, memory=None, clock=None):
        seen.update(registry=registry, memory=memory, clock=clock)

    shared = {"objects": "OBJ", "worlds": "WORLDS", "memory": "MEM"}
    spec = ModuleSpec("w", "m.w", "world", params={"registry": "worlds"})
    assert kwargs_for(wants, spec, shared) == {"registry": "WORLDS", "memory": "MEM"}
    spec2 = ModuleSpec("o", "m.o", "world", params={"registry": "objects"})
    hub = FakeHub()
    brain = Brain(hub, {}, [spec2], shared=shared, importer=fake_importer({"m.o": module(wants)}))
    run_brain(brain, 0.02)
    assert seen == {"registry": "OBJ", "memory": "MEM", "clock": None}


def test_select_modules_by_group_and_name():
    names = lambda ms: [m.name for m in ms]  # noqa: E731
    only_audio = select_modules({"audio"})
    assert only_audio and all(m.group == "audio" for m in only_audio)
    assert names(select_modules({"beat", "reset"})) == ["beat", "reset"]
    assert "serial_bridge" not in names(select_modules(skip={"bridge"}))
    assert names(select_modules({"bridge"})) == ["serial_bridge"]
    assert len(select_modules()) == len(wiring.MODULES)


def test_real_module_paths_resolve_or_are_known_pending():
    """Every listed module either imports and has run(), or belongs to a ticket not merged yet."""
    import importlib
    pending = {"server.gemini.scheduler", "server.gemini.talk"}
    for m in wiring.MODULES:
        try:
            mod = importlib.import_module(m.path)
        except ImportError:
            assert m.path in pending, f"{m.path} failed to import"
            continue
        assert callable(getattr(mod, "run", None)), f"{m.path} has no run()"
