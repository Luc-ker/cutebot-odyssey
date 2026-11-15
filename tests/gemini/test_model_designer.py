import asyncio
import json

from server.gemini.model_designer import (EXAMPLE, MAX_EXPANDED_PARTS, SCHEMA_PATH, ModelDesigner, design_prompt,
                                          normalise_recipe, request_model)

try:
    from server.common.schemas import validate_envelope
except ImportError:
    validate_envelope = None

WORLD = {"id": "w-1", "world": {"name": "Kingdom", "setting": "medieval kingdom", "palette": ["gold"]}}


def run(coro):
    return asyncio.run(coro)


class Hub:
    def __init__(self):
        self.subs, self.published = {}, []

    def sub(self, topic, cb):
        self.subs[topic] = cb

    async def pub(self, topic, data):
        self.published.append((topic, data))


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def objects_env(*objs, world_id="w-1"):
    return {"data": {"world_id": world_id, "objects": list(objs)}}


def obj(i, cls="bottle", role="watchtower", visible=True):
    return {"id": i, "cls": cls, "role": role, "name": f"Tower {i}", "behaviour": "friendly", "visible": visible,
            "pos": [0.5, 0.5], "size": [0.1, 0.3]}


def designer(tmp_path, request, config=None, **kw):
    hub = Hub()
    d = ModelDesigner(hub, {"MODEL_DESIGN_PER_MIN": 60, **(config or {})}, request=request,
                      fetch_snapshot=kw.pop("fetch_snapshot", None) or (lambda: _none()),
                      cache_path=tmp_path / "cache.json", clock=kw.pop("clock", Clock()), vocab=[], **kw).attach()
    run(hub.subs["world.current"]({"data": {"world": WORLD}}))
    return hub, d


async def _none():
    return None


# ------------------------------------------------------------------------------------- the guard

def test_example_and_schema_agree():
    assert normalise_recipe(EXAMPLE)["parts"][2]["repeat"] == {"count": 8, "mode": "ring", "radius": 0.22}
    schema = json.loads(SCHEMA_PATH.read_text())
    assert set(schema["properties"]["parts"]["items"]["properties"]["shape"]["enum"]) >= {"box", "cone", "dome"}


def test_normalise_clamps_and_drops_bad_parts():
    raw = {"name": "  a\n tower ", "animation": "dance", "parts": [
        {"shape": "box", "size": [5, -1, "x"], "pos": [3, -2, 0.1], "colour": "#ABCDEF", "material": "plasma",
         "rot": [400, 0, 0], "anim": "none"},
        {"shape": "teapot", "size": [0.1, 0.1, 0.1], "pos": [0, 0, 0], "colour": "#ffffff", "material": "stone"},
        {"shape": "cone", "size": [0.1, 0.1, 0.1], "pos": [0, 0, 0], "colour": "red", "material": "stone"},
        {"shape": "sphere", "size": [0.1, 0.1, 0.1], "pos": [0, 0, 0], "colour": "#00ff00", "material": "glow",
         "repeat": {"count": 99, "mode": "line"}, "anim": "flicker"},
    ]}
    r = normalise_recipe(raw)
    assert r["name"] == "a tower" and r["animation"] == "none"
    box, sphere = r["parts"]
    assert box["size"] == [1.2, 0.02, 0.2] and box["pos"] == [0.8, 0, 0.1] and box["rot"] == [180, 0, 0]
    assert box["colour"] == "#abcdef" and box["material"] == "stone" and "anim" not in box
    assert sphere["repeat"] == {"count": 12, "mode": "line", "spacing": 0.15} and sphere["anim"] == "flicker"
    assert normalise_recipe({"parts": []}) is None and normalise_recipe("nope") is None


def test_normalise_caps_expanded_parts():
    part = {"shape": "box", "size": [0.1] * 3, "pos": [0, 0, 0], "colour": "#123456", "material": "wood",
            "repeat": {"count": 12, "mode": "ring", "radius": 0.3}}
    r = normalise_recipe({"name": "x", "parts": [part] * 32})
    assert sum(p["repeat"]["count"] for p in r["parts"]) <= MAX_EXPANDED_PARTS


def test_prompt_mentions_object_role_and_proportion():
    text = design_prompt(WORLD, obj(1), {"role": "watchtower", "name": "Tower 1", "behaviour": "friendly"},
                         {"prompt": "a tall slender stone tower"})
    assert "bottle" in text and "watchtower" in text and "0.33 times as wide" in text
    assert "a tall slender stone tower" in text and "medieval kingdom" in text


def test_request_model_sends_schema_and_crop():
    seen = {}

    async def ask(parts, schema):
        seen["parts"], seen["schema"] = parts, schema
        return EXAMPLE

    r = run(request_model(WORLD, obj(1), {"role": "watchtower"}, b"fake-jpeg-bytes", ask=ask))
    assert r["name"] == "mossy watchtower"
    assert seen["schema"]["required"] == ["name", "parts"]
    assert seen["parts"][1]["inline_data"]["mime_type"] == "image/jpeg"


# ------------------------------------------------------------------------------------- the service

def test_designs_visible_objects_first_and_publishes_snapshot(tmp_path):
    calls = []

    async def request(world, o, role, image, info):
        calls.append(o["id"])
        return EXAMPLE

    hub, d = designer(tmp_path, request)
    run(hub.subs["world.objects"](objects_env(obj(1, visible=False), obj(2))))
    assert run(d.step()) is True
    assert calls == [2]
    snap = d.snapshot()
    assert [m["id"] for m in snap["models"]] == [2] and snap["models"][0]["source"] == "gemini"
    if validate_envelope:
        assert validate_envelope({"topic": "world.models", "ts": 1.0, "src": "t", "data": snap}) == []


def test_rate_limit_and_failure_retries(tmp_path):
    clock = Clock()
    calls = []

    async def request(world, o, role, image, info):
        calls.append(o["id"])
        return None  # bad answer

    hub, d = designer(tmp_path, request, config={"MODEL_DESIGN_PER_MIN": 6}, clock=clock)
    run(hub.subs["world.objects"](objects_env(obj(1), obj(2))))
    run(d.step())
    run(d.step())          # within 10 s of the last request: waits
    assert calls == [1]
    clock.t += 11
    run(d.step())          # object 1 failed recently, so object 2 goes next
    assert calls == [1, 2]
    clock.t += 31
    run(d.step()); clock.t += 11; run(d.step())
    clock.t += 31
    run(d.step()); clock.t += 11; run(d.step())
    assert calls.count(1) == 2 and calls.count(2) == 2  # MAX_ATTEMPTS, then given up


def test_stable_mode_designs_once_per_class(tmp_path):
    calls = []

    async def request(world, o, role, image, info):
        calls.append(o["id"])
        return EXAMPLE

    hub, d = designer(tmp_path, request, config={"STABLE_KINGDOM_ENABLED": True})
    run(hub.subs["world.objects"](objects_env(obj(1), obj(2))))
    run(d.step())
    assert run(d.step()) is False
    assert len(calls) == 1 and len(d.snapshot()["models"]) == 2  # both bottles share one design


def test_cache_reuse_after_enough_variants_and_survives_restart(tmp_path):
    calls = []

    async def request(world, o, role, image, info):
        calls.append(o["id"])
        return dict(EXAMPLE, name=f"tower {o['id']}")

    clock = Clock()
    hub, d = designer(tmp_path, request, config={"MODEL_VARIANTS_PER_ROLE": 2}, clock=clock)
    run(hub.subs["world.objects"](objects_env(obj(1), obj(2), obj(3))))
    for _ in range(3):
        run(d.step())
        clock.t += 2
    assert calls == [1, 2]                       # the third reuses one of the two cached designs
    assert d.snapshot()["models"][2]["recipe"]["name"] in {"tower 1", "tower 2"}

    calls.clear()
    hub2, d2 = designer(tmp_path, request, config={"MODEL_VARIANTS_PER_ROLE": 2})
    run(hub2.subs["world.objects"](objects_env(obj(9))))
    run(d2.step())
    assert calls == [] and len(d2.snapshot()["models"]) == 1  # from logs/model_cache.json, no Gemini call


def test_disabled_designer_only_reuses(tmp_path):
    async def request(*a):
        raise AssertionError("must not call Gemini")

    hub, d = designer(tmp_path, request, config={"MODEL_DESIGN_ENABLED": False})
    run(hub.subs["world.objects"](objects_env(obj(1))))
    assert run(d.step()) is False
