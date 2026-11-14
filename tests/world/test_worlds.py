"""T54 — world registry and returning-song match."""
import asyncio
import random

from server.world.worlds import WorldRegistry, _local_distance

S = {"tempo_bpm": 120.0, "energy": 0.7, "brightness": 0.6,
     "chroma": [0.9, 0.1, 0.3, 0.0, 0.5, 0.2, 0.1, 0.8, 0.0, 0.3, 0.1, 0.2]}
FAR = {"tempo_bpm": 70.0, "energy": 0.1, "brightness": 0.1,
       "chroma": [0.0, 0.8, 0.0, 0.9, 0.0, 0.1, 0.9, 0.0, 0.7, 0.0, 0.8, 0.0]}


def noisy(sig, amount=0.03, seed=1):
    rnd = random.Random(seed)
    return {"tempo_bpm": sig["tempo_bpm"] * (1 + rnd.uniform(-amount, amount)),
            "energy": sig["energy"] + rnd.uniform(-amount, amount),
            "brightness": sig["brightness"] + rnd.uniform(-amount, amount),
            "chroma": [max(0.0, c + rnd.uniform(-amount, amount)) for c in sig["chroma"]]}


def world(name, sig=None, wid=None):
    w = {"world": {"name": name, "setting": name}, "music_signature": sig}
    if wid:
        w["id"] = wid
    return w


def test_match_returning_song():
    reg = WorldRegistry({"RETURN_MATCH_THRESHOLD": 0.25}, distance=_local_distance)
    a = reg.add(world("ocean", S))
    reg.add(world("wasteland", FAR))
    assert reg.match(noisy(S)) is a
    very_different = {"tempo_bpm": 200.0, "energy": 0.0, "brightness": 1.0, "chroma": [1.0] + [0.0] * 11}
    assert reg.match(very_different) is None


def test_assigns_id_and_get():
    reg = WorldRegistry()
    w = reg.add(world("snow", S))
    assert w["id"].startswith("w-") and len(w["id"]) == 10
    assert reg.get(w["id"]) is w
    kept = reg.add(world("city", FAR, wid="w-12345678"))
    assert kept["id"] == "w-12345678" and len(reg.all()) == 2


def test_fallbacks_never_matched_and_survive_reset():
    reg = WorldRegistry(distance=_local_distance)
    fb = reg.add(world("kingdom", S), fallback=True)
    assert reg.match(S) is None
    assert reg.get_by_name("kingdom") is fb
    session = reg.add(world("ocean", S))
    assert reg.match(S) is session

    class Hub:
        def __init__(self):
            self.subs = {}

        def sub(self, p, cb):
            self.subs[p] = cb

    from server.world import worlds as mod
    hub = Hub()
    asyncio.run(mod.run(hub, {}, registry=reg))
    asyncio.run(hub.subs["system.reset"]({"data": {}}))
    assert reg.get(session["id"]) is None and reg.get(fb["id"]) is fb


def test_uses_injected_distance():
    reg = WorldRegistry({"RETURN_MATCH_THRESHOLD": 0.5}, distance=lambda a, b: 0.1)
    w = reg.add(world("any", S))
    assert reg.match(FAR) is w
