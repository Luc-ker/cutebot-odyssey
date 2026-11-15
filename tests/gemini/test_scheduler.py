import asyncio

from server.audio.signature import distance
from server.gemini.scheduler import WorldScheduler
from server.world.worlds import WorldRegistry

SIG = {"tempo_bpm": 120.0, "energy": 0.6, "brightness": 0.5,
       "chroma": [1.0] + [0.0] * 11}


class Hub:
    def __init__(self):
        self.messages = []

    async def pub(self, topic, data):
        self.messages.append((topic, data))


class Audio:
    rate = 44100

    def last(self, _seconds):
        return [0.1, 0.2]


class Clips:
    def get_clip(self, _seconds):
        return b"wav"


def world(name, setting, signature=SIG):
    return {
        "id": "w-1234abcd", "world": {"name": name, "setting": setting, "mood": "bright",
                                          "time_of_day": "day", "weather": "clear",
                                          "palette": ["blue", "green", "gold"]},
        "roles": [], "terrain": {"open_space": "plain", "under_table": "cave"},
        "restyle_prompt": "First-person low view.", "narration": "Welcome.", "music_signature": dict(signature),
    }


def build_scheduler(compose, *, registry=None, distance_fn=None):
    hub = Hub()
    scheduler = WorldScheduler(
        hub, {"GEMINI_INTERVAL_S": 8, "CLIP_SECONDS": 7, "WORLD_CHANGE_THRESHOLD": 0.35},
        audio_input=Audio(), clip_store=Clips(), world_registry=registry,
        compose=compose, guard=lambda raw, _objects, _vocab: raw,
        signature_fn=lambda _samples, _rate: dict(SIG), distance_fn=distance_fn or distance,
        snapshot_fetcher=lambda _config: b"jpg",
    )
    return hub, scheduler


def test_adopts_different_world_but_holds_similar_response():
    responses = iter([world("Ocean", "open ocean"), world("Another Sea", "open ocean")])

    async def compose(*_args):
        return next(responses)

    hub, scheduler = build_scheduler(compose, distance_fn=lambda _a, b: 0.8 if b.get("tempo_bpm") == 104 else 0.1)
    async def scenario():
        await scheduler.start()
        scheduler.silent = False
        assert await scheduler.request_world(now=10) is True
        assert scheduler.current["world"]["setting"] == "open ocean"
        assert await scheduler.request_world(now=15) is False
        assert scheduler.current["world"]["name"] == "Ocean"
    asyncio.run(scenario())
    assert len([message for message in hub.messages if message[0] == "world.current"]) == 2


def test_timeout_switches_to_a_built_in_scene():
    async def compose(*_args):
        raise TimeoutError("slow")

    hub, scheduler = build_scheduler(compose)
    async def scenario():
        await scheduler.start()
        before = scheduler.current["id"]
        scheduler.silent = False
        assert await scheduler.request_world(now=10) is True
        assert scheduler.current["id"] != before
        assert scheduler.world_registry.is_fallback(scheduler.current["id"])
    asyncio.run(scenario())
    assert len([message for message in hub.messages if message[0] == "world.current"]) == 2


def test_returning_signature_reuses_world_without_composition():
    registry = WorldRegistry({"RETURN_MATCH_THRESHOLD": 0.15}, distance=lambda _a, _b: 0.0)
    returning = registry.add(world("Saved Ocean", "open ocean"))

    async def should_not_compose(*_args):
        raise AssertionError("returning songs should not call Gemini")

    hub, scheduler = build_scheduler(should_not_compose, registry=registry)
    async def scenario():
        await scheduler.start()
        scheduler.silent = False
        assert await scheduler.request_world(now=10) is True
        assert scheduler.current["id"] == returning["id"]
    asyncio.run(scenario())
    events = [data for topic, data in hub.messages if topic == "world.event"]
    assert events[-1]["returning"] is True

def test_first_generated_world_replaces_fallback_even_with_similar_setting_and_music():
    previous = []

    async def compose(_audio, _image, _objects, current):
        previous.append(current)
        return world("The Music Kingdom", "medieval kingdom")

    hub, scheduler = build_scheduler(compose, distance_fn=lambda _a, _b: 0.0)

    async def scenario():
        await scheduler.start()
        fallback_id = scheduler.current["id"]
        scheduler.silent = False
        assert await scheduler.request_world(now=10) is True
        assert scheduler.current["id"] != fallback_id
        assert not scheduler.world_registry.is_fallback(scheduler.current["id"])
        assert scheduler.current["world"]["name"] == "The Music Kingdom"
        assert previous == [None]
        # Once grounded in this music, repeating it holds the generated world without asking Gemini.
        assert await scheduler.request_world(now=20) is False
        assert len(previous) == 1
        # A detected song change asks Gemini without the current world, and always takes the answer.
        assert await scheduler.request_world(now=30, song_change=True) is True
        assert previous[1] is None

    asyncio.run(scenario())


def test_no_music_run_never_opens_microphone_and_reset_restores_kingdom(monkeypatch):
    from server.gemini import scheduler as module
    from server.audio import capture

    def forbidden_audio(*_args, **_kwargs):
        raise AssertionError("no-music mode must not allocate a microphone")

    async def forbidden_composition(*_args, **_kwargs):
        raise AssertionError("no-music mode must not request a music world")

    class SubHub(Hub):
        def __init__(self):
            super().__init__()
            self.handlers = {}

        def sub(self, topic, callback):
            self.handlers[topic] = callback

    monkeypatch.setattr(capture, "AudioInput", forbidden_audio)
    monkeypatch.setattr(module.WorldScheduler, "request_world", forbidden_composition)
    monkeypatch.setattr(module, "LOOP_SLEEP_S", 0.001)

    async def scenario():
        hub = SubHub()
        task = asyncio.create_task(module.run(hub, {"MUSIC_ENABLED": False}))
        try:
            await asyncio.sleep(0.02)
            assert not task.done()
            assert "audio.features" not in hub.handlers
            worlds = [d["world"] for t, d in hub.messages if t == "world.current"]
            assert worlds[-1]["world"]["name"] == "Kingdom"
            await hub.handlers["system.reset"]({"data": {}})
            worlds = [d["world"] for t, d in hub.messages if t == "world.current"]
            assert len(worlds) >= 2
            assert worlds[-1]["world"]["name"] == "Kingdom"
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    asyncio.run(scenario())


def _composing(hub):
    return [data for topic, data in hub.messages if topic == "world.composing"]


def test_world_composing_reports_rendering_then_new_scene_then_kept():
    responses = iter([world("Ocean", "open ocean"), world("Another Sea", "open ocean")])

    async def compose(*_args):
        return next(responses)

    hub, scheduler = build_scheduler(compose, distance_fn=lambda _a, b: 0.8 if b.get("tempo_bpm") == 104 else 0.1)

    async def scenario():
        await scheduler.start()
        assert _composing(hub) == []  # adopting the starting world is not music-driven
        scheduler.silent = False
        await scheduler.request_world(now=10)
        await scheduler.request_world(now=15)
    asyncio.run(scenario())
    # The second check hears the same song, so it holds quietly: no Gemini call, nothing on screen.
    assert _composing(hub) == [{"state": "composing"}, {"state": "done", "name": "Ocean"}]


def test_world_composing_reports_failure_and_returning_worlds_skip_rendering():
    async def compose(*_args):
        raise TimeoutError("slow")

    hub, scheduler = build_scheduler(compose)

    async def failing():
        await scheduler.start()
        scheduler.silent = False
        await scheduler.request_world(now=10)
    asyncio.run(failing())
    composing = _composing(hub)
    assert composing[0] == {"state": "composing"} and composing[1]["state"] == "done"
    assert composing[1]["name"] != "Kingdom"  # Gemini failed, so a built-in scene took over

    registry = WorldRegistry({"RETURN_MATCH_THRESHOLD": 0.15}, distance=lambda _a, _b: 0.0)
    registry.add(world("Saved Ocean", "open ocean"))
    hub, scheduler = build_scheduler(compose, registry=registry)

    async def returning():
        await scheduler.start()
        scheduler.silent = False
        await scheduler.request_world(now=10)
    asyncio.run(returning())
    assert _composing(hub) == [{"state": "done", "name": "Saved Ocean"}]


def test_song_change_always_renders_a_new_scene_even_when_the_music_looks_similar():
    responses = iter([world("Ocean", "open ocean"), world("Ember Forge", "volcanic forge")])
    calls = []

    async def compose(*_args):
        calls.append(1)
        return next(responses)

    hub, scheduler = build_scheduler(compose, distance_fn=lambda _a, b: 0.8 if b.get("tempo_bpm") == 104 else 0.1)

    async def scenario():
        await scheduler.start()
        scheduler.silent = False
        assert await scheduler.request_world(now=10) is True
        assert await scheduler.request_world(now=20) is False          # timed check, same song: held
        assert await scheduler.request_world(now=30, song_change=True) is True
        assert scheduler.current["world"]["name"] == "Ember Forge"
    asyncio.run(scenario())
    assert len(calls) == 2
    assert _composing(hub)[-1] == {"state": "done", "name": "Ember Forge"}


def test_listening_is_never_on_without_a_microphone():
    async def compose(*_args):
        return None

    hub, scheduler = build_scheduler(compose)
    scheduler.can_listen = False

    async def scenario():
        await scheduler.set_show({"listening": True})
    asyncio.run(scenario())
    assert hub.messages[-1] == ("show.state", {"running": True, "listening": False, "can_listen": False})


def test_gemini_repeating_the_current_setting_forces_a_built_in_scene_and_never_kept():
    responses = iter([world("Ocean", "open ocean"), world("Another Sea", "open ocean")])

    async def compose(*_args):
        return next(responses)

    hub, scheduler = build_scheduler(compose, distance_fn=lambda _a, _b: 0.0)

    async def scenario():
        await scheduler.start()
        scheduler.silent = False
        assert await scheduler.request_world(now=10) is True
        assert scheduler.current["world"]["name"] == "Ocean"
        assert await scheduler.request_world(now=20, song_change=True) is True
        assert scheduler.world_registry.is_fallback(scheduler.current["id"])
        assert scheduler.current["world"]["name"] not in ("Ocean", "Another Sea")
        # Same song keeps playing: the built-in scene holds instead of flipping every check.
        assert await scheduler.request_world(now=40) is False
    asyncio.run(scenario())
    assert all(d["state"] != "kept" for d in _composing(hub))


def test_forced_built_in_scenes_rotate_instead_of_repeating():
    async def compose(*_args):
        raise TimeoutError("quota")

    hub, scheduler = build_scheduler(compose)
    picked = []

    async def scenario():
        await scheduler.start()
        scheduler.silent = False
        for i in range(4):
            assert await scheduler.request_world(now=10 + 10 * i, song_change=True) is True
            picked.append(scheduler.current["world"]["name"])
    asyncio.run(scenario())
    assert len(set(picked)) == 4  # no repeats while three others are recent


def _clocked(compose):
    hub, scheduler = build_scheduler(compose)
    t = [100.0]
    scheduler.clock = lambda: t[0]
    return hub, scheduler, t


def _show_states(hub):
    return [d for topic, d in hub.messages if topic == "show.state"]


def test_music_alone_never_changes_the_scene_without_a_listen_press():
    calls = []

    async def compose(*_args):
        calls.append(1)
        return world("Ember Forge", "volcanic forge")

    hub, scheduler, t = _clocked(compose)

    async def scenario():
        await scheduler.start()
        scheduler.on_audio_features({"silent": False})
        for now in range(100, 200, 4):
            await scheduler.tick(float(now))
        scheduler.on_audio_features({"silent": True})       # long silence: no return to the Kingdom either
        await scheduler.tick(300.0)
    asyncio.run(scenario())
    assert calls == []
    assert scheduler.current["world"]["name"] == "Kingdom"


def test_listen_press_hears_one_window_then_changes_the_scene_once_and_stops():
    calls = []

    async def compose(*_args):
        calls.append(1)
        return world("Ember Forge", "volcanic forge")

    hub, scheduler, t = _clocked(compose)

    async def scenario():
        await scheduler.start()
        await scheduler.set_show({"listening": True})       # pressed at t=100
        assert scheduler.listening is True
        scheduler.on_audio_features({"silent": False})
        await scheduler.tick(103.0)
        assert calls == []                                  # still filling the 7 s window
        scheduler.on_audio_features({"silent": True})       # a pause right at the end doesn't cancel it
        await scheduler.tick(107.0)
        assert calls == [1]
        assert scheduler.current["world"]["name"] == "Ember Forge"
        assert scheduler.listening is False
        scheduler.on_audio_features({"silent": False})
        for now in range(110, 200, 4):                      # music keeps playing: no more changes
            await scheduler.tick(float(now))
        assert calls == [1]
        await scheduler.set_show({"listening": True})       # the same song again still changes on a press
        t[0] = 200.0
        await scheduler.set_show({"listening": False})      # pressed again: cancelled
        await scheduler.tick(210.0)
        assert calls == [1]
    asyncio.run(scenario())
    assert _composing(hub)[-1] == {"state": "done", "name": "Ember Forge"}
    assert _show_states(hub)[-1] == {"running": True, "listening": False, "can_listen": True}


def test_listen_press_that_hears_no_music_keeps_the_scene_and_says_so():
    calls = []

    async def compose(*_args):
        calls.append(1)
        return world("Ember Forge", "volcanic forge")

    hub, scheduler, t = _clocked(compose)

    async def scenario():
        await scheduler.start()
        await scheduler.set_show({"listening": True})
        scheduler.on_audio_features({"silent": True})
        await scheduler.tick(107.0)
    asyncio.run(scenario())
    assert calls == []
    assert scheduler.current["world"]["name"] == "Kingdom"
    assert _composing(hub)[-1] == {"state": "quiet"}
    assert scheduler.listening is False


def test_show_state_and_stopping_the_show_cancels_listening():
    calls = []

    async def compose(*_args):
        calls.append(1)
        return world("Ember Forge", "volcanic forge")

    hub, scheduler, t = _clocked(compose)

    async def scenario():
        await scheduler.start()
        await scheduler.set_show({})                        # a page asking for the state
        await scheduler.set_show({"listening": True})
        scheduler.on_audio_features({"silent": False})
        await scheduler.set_show({"running": False})        # stopping the show cancels the window
        await scheduler.set_show({"listening": True})       # and listen does nothing while stopped
        await scheduler.tick(120.0)
        assert calls == []
        await scheduler.set_show({"running": True})
        await scheduler.tick(140.0)
        assert calls == []                                  # starting the show doesn't listen by itself
    asyncio.run(scenario())
    states = _show_states(hub)
    assert states[0] == {"running": True, "listening": False, "can_listen": True}
    assert states[1]["listening"] is True
    assert states[2] == {"running": False, "listening": False, "can_listen": True}
    assert states[3] == {"running": False, "listening": False, "can_listen": True}


def test_a_scene_that_arrives_after_the_listen_press_is_cancelled_is_dropped():
    hub, scheduler, t = _clocked(None)

    async def compose(*_args):
        await scheduler.set_show({"listening": False})      # pressed again while Gemini was working
        return world("Ember Forge", "volcanic forge")
    scheduler.compose = compose

    async def scenario():
        await scheduler.start()
        await scheduler.set_show({"listening": True})
        scheduler.on_audio_features({"silent": False})
        await scheduler.tick(107.0)
    asyncio.run(scenario())
    assert scheduler.current["world"]["name"] == "Kingdom"
