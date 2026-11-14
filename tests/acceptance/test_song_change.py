"""T107 — acceptance: changing the music changes the world; the first song brings the first world back
(whitepaper §7.6, §7.7, §7.12).

Real hub, real world registry (T54), role memory (T49), arrivals (T50), objects publisher (T62) and
transition coordinator (T95); the real music signature (T70) over synthetic songs from ``FakeAudio``; a
scripted ``FakeGemini``; and the T74 scheduler stand-in from ``fakes.py``, stepped with ``tick()`` instead of
waiting ``GEMINI_INTERVAL_S`` between calls.

Phases: start in the kingdom fallback world → song A (sea shanty) adopts world A with its roles → song B
(heavy metal) adopts world B through a ``world.transition`` with new roles → song A again re-adopts world A
with ``world_changed {returning: true}``, the original roles and no Gemini call. Timeout case: Gemini never
answers → the world holds and Gemini is reported unhealthy.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fakes  # noqa: E402
from fakes import FakeAudio, FakeGemini, Harness, make_world, role_of  # noqa: E402
from server.world import arrivals, objects_publisher, transitions  # noqa: E402
from server.world.memory import RoleMemory  # noqa: E402
from server.world.registry import ObjectRegistry  # noqa: E402
from server.world.worlds import WorldRegistry  # noqa: E402

CHAIR, BOTTLE = 1, 2

OCEAN = make_world("The Drowned Kingdom", "stormy open ocean",
                   [(CHAIR, "ship", "the Gull", "neutral"), (BOTTLE, "lighthouse", "the Old Lamp", "friendly")],
                   palette=["ocean blue", "storm grey", "lantern gold"], open_space="open sea")
WASTES = make_world("The Ember Wastes", "volcanic wasteland",
                    [(CHAIR, "fortress", "Blackspire", "neutral"), (BOTTLE, "tower", "the Ash Spire", "friendly")],
                    palette=["lava red", "volcanic black", "ember orange"], open_space="cracked basalt")
NEON = make_world("Neon Sprawl", "neon city", [(CHAIR, "skyscraper", "Arc Tower", "neutral")])


def roles(world_objects):
    return {oid: role_of(world_objects, oid) for oid in (CHAIR, BOTTLE)}


def expected(raw):
    return {r["object_id"]: (r["role"], r["name"], r["behaviour"]) for r in raw["roles"]}


async def run_song_change():
    config = fakes.test_config(GEMINI_TIMEOUT_S=0.5)
    audio = FakeAudio()
    gemini = FakeGemini(audio)
    gemini.worlds = {"sea_shanty": OCEAN, "heavy_metal": WASTES, "synthwave": NEON}
    memory, registry, worlds = RoleMemory(), ObjectRegistry(config), WorldRegistry(config)

    async with Harness(config) as h:
        sched = fakes.make_scheduler(await h.client("scheduler"), config, audio=audio, gemini=gemini,
                                     worlds=worlds, memory=memory, registry=registry)
        await h.start("arrivals", arrivals.run, registry=registry, memory=memory, request_role=gemini.request_role)
        await h.start("objects_publisher", objects_publisher.run, registry=registry, memory=memory)
        await h.start("transitions", transitions.run)
        await h.settle()

        # start-up: the kingdom fallback world, a chair and a bottle on the table
        await h.pub("world.select", {"name": "kingdom"})
        kingdom = (await h.wait_for("world.current")).data["world"]
        h.scene.put(CHAIR, "chair", (0.3, 0.4), (0.12, 0.14))
        h.scene.put(BOTTLE, "bottle", (0.7, 0.6), (0.05, 0.08))
        h.feeding = True
        await h.wait_for("world.objects", lambda d: all(roles(d).values()), timeout=5)

        # ---- phase 1: song A → world A ----------------------------------------------------------------
        audio.play("sea_shanty")
        m = h.mark()
        assert await sched.tick() == "adopted"
        cur = (await h.wait_for("world.current", after=m)).data
        world_a = cur["world"]
        assert world_a["world"]["name"] == "The Drowned Kingdom"
        assert cur["previous_id"] == kingdom["id"]
        changed = await h.wait_for("world.event", lambda d: d.get("kind") == "world_changed", after=m)
        assert changed.data == {"kind": "world_changed", "world_id": world_a["id"], "returning": False}
        tr = await h.wait_for("world.transition", after=m)
        assert tr.data["to"]["id"] == world_a["id"] and tr.data["from"]["id"] == kingdom["id"]
        objs = await h.wait_for("world.objects", lambda d: d["world_id"] == world_a["id"] and roles(d) == expected(OCEAN),
                                after=m, timeout=2)
        roles_a = roles(objs.data)

        # ---- phase 2: song B → world B, through a transition, with new roles ---------------------------
        audio.play("heavy_metal")
        m = h.mark()
        assert await sched.tick() == "adopted"
        world_b = (await h.wait_for("world.current", after=m)).data["world"]
        assert world_b["id"] != world_a["id"] and world_b["world"]["setting"] == "volcanic wasteland"
        tr = await h.wait_for("world.transition", after=m)
        assert tr.data["from"]["id"] == world_a["id"] and tr.data["to"]["id"] == world_b["id"]
        assert tr.data["duration_ms"] == int(config.get("TRANSITION_MS", 3000))
        await h.wait_for("world.event", lambda d: d.get("kind") == "world_changed"
                         and d["world_id"] == world_b["id"] and d["returning"] is False, after=m)
        objs = await h.wait_for("world.objects", lambda d: d["world_id"] == world_b["id"] and all(roles(d).values()),
                                after=m, timeout=2)
        roles_b = roles(objs.data)
        assert roles_b == expected(WASTES)
        assert roles_b != roles_a

        # ---- phase 3: song A again → world A returns with its roles, without asking Gemini ---------------
        audio.play("sea_shanty")
        calls = gemini.compose_calls
        m = h.mark()
        assert await sched.tick() == "returned"
        assert gemini.compose_calls == calls, "a returning song must not call Gemini"
        cur = (await h.wait_for("world.current", after=m)).data
        assert cur["world"]["id"] == world_a["id"] and cur["previous_id"] == world_b["id"]
        await h.wait_for("world.event", lambda d: d.get("kind") == "world_changed"
                         and d["world_id"] == world_a["id"] and d["returning"] is True, after=m)
        tr = await h.wait_for("world.transition", after=m)
        assert tr.data["from"]["id"] == world_b["id"] and tr.data["to"]["id"] == world_a["id"]
        objs = await h.wait_for("world.objects", lambda d: d["world_id"] == world_a["id"] and all(roles(d).values()),
                                after=m, timeout=2)
        assert roles(objs.data) == roles_a, "the returning world must bring back its original roles"

        # ---- timeout: Gemini never answers → the world holds -------------------------------------------
        gemini.mode = "timeout"
        audio.play("synthwave")
        m = h.mark()
        assert await sched.tick() == "failed"
        await h.wait_for("system.health", lambda d: d.get("service") == "gemini" and d["ok"] is False, after=m)
        await h.settle(0.5)
        assert not h.find("world.current", after=m), "a Gemini timeout must not change the world"
        assert not h.find("world.transition", after=m)
        objs = await h.latest("world.objects")
        assert objs["world_id"] == world_a["id"] and roles(objs) == roles_a

        h.assert_no_errors()


def test_song_change_and_return():
    asyncio.run(run_song_change())


def test_similar_music_keeps_the_world():
    """Same song, a new Gemini answer with a different setting: the music didn't change, so the world holds."""

    async def go():
        config = fakes.test_config()
        audio = FakeAudio()
        gemini = FakeGemini(audio)
        gemini.worlds = {"sea_shanty": OCEAN}
        async with Harness(config) as h:
            sched = fakes.make_scheduler(await h.client("scheduler"), config, audio=audio, gemini=gemini,
                                         worlds=WorldRegistry(config), memory=RoleMemory(),
                                         registry=ObjectRegistry(config))
            await h.settle()
            audio.play("sea_shanty")
            assert await sched.tick() == "adopted"
            gemini.worlds["sea_shanty"] = WASTES        # Gemini changes its mind, the music didn't
            audio.play("sea_shanty")                    # same song, later in it
            m = h.mark()
            assert await sched.tick() == "held"
            await h.settle(0.3)
            assert not [x for x in h.find("world.current", after=m)
                        if x.data["world"]["world"]["setting"] != OCEAN["world"]["setting"]]
            h.assert_no_errors()

    asyncio.run(go())
