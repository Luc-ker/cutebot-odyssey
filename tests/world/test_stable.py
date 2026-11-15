"""Stable Kingdom demo mode: one prompt, settled objects, per-class roles, no giants."""
import asyncio
import json

from server.common.config import load_config
from server.world import giants, prompt_blend, stable
from server.world.arrivals import Arrivals
from server.world.fallback_roles import class_role
from server.world.memory import RoleMemory
from server.world.prompt_composer import PromptComposer
from server.world.registry import ObjectRegistry
from tests.world.test_arrivals import FakeHub, _settle, vstate

KINGDOM = json.load(open(stable.__file__.replace("server/world/stable.py", "shared/worlds/kingdom.json")))
STABLE = {"STABLE_KINGDOM_ENABLED": True, "STABLE_KINGDOM_PROMPT": "a miniature kingdom",
          "OBJECT_SETTLE_S": 1.0, "VIEW_GRACE_S": 0.3, "OBJECT_FORGET_S": 5}


def test_shipped_config_turns_stable_mode_on_with_a_miniature_kingdom_prompt():
    cfg = load_config(env={})
    assert stable.enabled(cfg)
    text = stable.prompt(cfg)
    assert len(text) <= 750
    for phrase in ("fairy-tale", "kingdom", "watchtower", "fortress walls", "cave", "castle",
                   "camera movement", "the output will show"):
        assert phrase in text.lower()
    # Naming real objects makes the renderer draw them inside the kingdom, so the prompt never does.
    for word in ("bottle", "laptop", "desk", "table"):
        assert word not in text.lower()


def test_stable_mode_is_off_without_the_key_and_prompt_falls_back():
    assert not stable.enabled({})
    assert stable.prompt({"STABLE_KINGDOM_PROMPT": "  "}) == stable.DEFAULT_PROMPT
    assert stable.settle_s({"OBJECT_SETTLE_S": "bad"}) == stable.DEFAULT_SETTLE_S


def test_composer_prompt_never_changes_in_stable_mode():
    c = PromptComposer(vocab={"watchtower": "a tall watchtower"}, fixed_prompt="a miniature kingdom")
    out = [c.tick(0.0)]
    c.on_world_current({"world": KINGDOM})
    c.on_world_objects({"world_id": KINGDOM["id"], "objects": [{"id": 1, "role": "watchtower"}]})
    c.on_robot_state({"facing_id": 1})
    out.append(c.tick(1.0))
    c.on_world_event({"kind": "giant_enter", "id": "g1"})
    out.append(c.tick(2.0))
    c.on_transition({"started": 3.0, "duration_ms": 3000, "to": {"id": "w-x", "restyle_prompt": "ocean"}}, 3.0)
    out.append(c.tick(3.5))
    c.reset()
    out.append(c.tick(10.0))
    # Published once at start and once after reset; never anything else.
    assert [o for o in out if o is not None] == ["a miniature kingdom", "a miniature kingdom"]
    assert c.current_text() == "a miniature kingdom"


def test_blender_and_giant_events_are_off_in_stable_mode():
    hub = FakeHub()
    asyncio.run(asyncio.wait_for(prompt_blend.run(hub, STABLE), 1))
    asyncio.run(asyncio.wait_for(giants.run(hub, STABLE), 1))
    assert hub.subs == []  # no transitions blended, no giant_enter ever published


def _arrivals(request_role=None):
    hub = FakeHub()
    arr = Arrivals(hub, STABLE, registry=ObjectRegistry(STABLE), memory=RoleMemory(),
                   request_role=request_role, clock=lambda: 0.0).attach()
    arr.set_world(KINGDOM)
    return hub, arr


def test_short_detection_gets_no_role_and_no_event():
    calls = []

    async def gemini(*a):
        calls.append(a)

    async def main():
        hub, arr = _arrivals(request_role=gemini)
        for i in range(5):  # 0.4 s of a bottle, then it is gone
            arr.handle_vision(vstate([(1, "bottle")]), i * 0.1)
        for i in range(5, 40):
            arr.handle_vision(vstate([]), i * 0.1)
        arr.handle_vision(vstate([]), 10.0)  # forgotten
        await _settle(arr)
        assert hub.events("object_added") == [] and hub.events("object_removed") == []
        assert calls == []
    asyncio.run(main())


def test_flicker_restarts_the_settle_clock():
    async def main():
        hub, arr = _arrivals()
        t = 0.0
        for _ in range(3):  # seen 0.8 s, gone 0.5 s (past the 0.3 s grace), repeatedly
            for _ in range(8):
                arr.handle_vision(vstate([(1, "bottle")]), t); t += 0.1
            for _ in range(5):
                arr.handle_vision(vstate([]), t); t += 0.1
        await _settle(arr)
        assert hub.events("object_added") == []
        for _ in range(12):  # 1.1 s continuously in view
            arr.handle_vision(vstate([(1, "bottle")]), t); t += 0.1
        await _settle(arr)
        assert [e["id"] for e in hub.events("object_added")] == [1]
    asyncio.run(main())


def test_settled_objects_get_one_local_role_per_class_and_no_gemini_call():
    calls = []

    async def gemini(*a):
        calls.append(a)
        return {"role": "dragon", "name": "Surprise", "behaviour": "threat"}

    async def main():
        hub, arr = _arrivals(request_role=gemini)
        for i in range(12):
            arr.handle_vision(vstate([(1, "bottle"), (2, "bottle"), (3, "laptop")]), i * 0.1)
        await _settle(arr)
        added = {e["id"]: e for e in hub.events("object_added")}
        assert sorted(added) == [1, 2, 3]
        assert added[1]["role"] == added[2]["role"] == class_role(KINGDOM, "bottle")["role"] == "watchtower"
        assert added[3]["role"] == class_role(KINGDOM, "laptop")["role"]
        assert calls == []
        # Seen again later: same id, same role, not announced twice.
        arr.handle_vision(vstate([(1, "bottle")]), 2.0)
        await _settle(arr)
        assert len(hub.events("object_added")) == 3
    asyncio.run(main())


def test_class_role_ignores_object_id_and_taken_roles():
    assert class_role(KINGDOM, "bottle") == class_role(KINGDOM, "Bottle")
    assert class_role(KINGDOM, "bottle")["role"] == "watchtower"


def test_scheduler_adoption_gives_unsettled_objects_no_role(monkeypatch):
    from server.gemini.scheduler import WorldScheduler

    async def main():
        hub = FakeHub()
        sched = WorldScheduler(hub, dict(STABLE), vocab=[])
        sched.on_vision_state(vstate([(1, "bottle")]), 0.0)
        await sched.start()
        current = [d for t, d in hub.published if t == "world.current"][-1]["world"]
        assert current["world"]["name"] == "Kingdom" and current["roles"] == []
    asyncio.run(main())


def test_renderer_config_exposes_effective_stable_settings(monkeypatch):
    from server.hub.restyle import renderer_config

    monkeypatch.setenv("GENRATOR_STABLE_KINGDOM_ENABLED", "false")
    assert renderer_config()["STABLE_KINGDOM_ENABLED"] is False
    monkeypatch.setenv("GENRATOR_STABLE_KINGDOM_ENABLED", "true")
    cfg = renderer_config()
    assert cfg["STABLE_KINGDOM_ENABLED"] is True and "fairy-tale" in cfg["STABLE_KINGDOM_PROMPT"]
    assert not any("KEY" in k for k in cfg)
    monkeypatch.delenv("GENRATOR_DECART_MODEL", raising=False)
    assert renderer_config()["DECART_MODEL"] == "lucy-2.6"
