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


def test_timeout_keeps_current_world():
    async def compose(*_args):
        raise TimeoutError("slow")

    hub, scheduler = build_scheduler(compose)
    async def scenario():
        await scheduler.start()
        before = scheduler.current["id"]
        scheduler.silent = False
        assert await scheduler.request_world(now=10) is False
        assert scheduler.current["id"] == before
    asyncio.run(scenario())
    assert len([message for message in hub.messages if message[0] == "world.current"]) == 1


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