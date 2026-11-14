"""T57 — danger and friendly proximity events."""
from server.world.proximity import Proximity

CFG = {"DANGER_RADIUS": 0.1, "FRIENDLY_RADIUS": 0.08}
DRAGON = {"id": 5, "pos": [0.5, 0.5], "size": [0.04, 0.04], "role": "dragon", "name": "Ember", "behaviour": "threat"}
TOWER = {"id": 6, "pos": [0.5, 0.9], "size": [0.0, 0.0], "role": "lighthouse", "name": "Old Beacon",
         "behaviour": "friendly"}
WORLD_OBJECTS = {"objects": [DRAGON, TOWER], "clusters": []}


def robot(x, y, seen=True):
    return {"pos": [x, y], "heading": 0.0, "seen": seen}


def drive(prox, xs, y=0.5, t0=0.0, dt=0.1, seen=True):
    events = []
    for i, x in enumerate(xs):
        events += prox.update(robot(x, y, seen), WORLD_OBJECTS, t0 + i * dt)
    return events


def path(a, b, steps=60):
    return [a + (b - a) * i / steps for i in range(steps + 1)]


def test_path_through_threat_one_enter_one_exit():
    events = drive(Proximity(CFG), path(0.1, 0.9))
    kinds = [e["kind"] for e in events]
    assert kinds == ["danger_enter", "danger_exit"]
    assert events[0] == {"kind": "danger_enter", "id": 5, "name": "Ember", "role": "dragon"}


def test_hysteresis_near_the_edge():
    prox = Proximity(CFG)
    r = 0.1 + 0.02
    # wobble just inside / just outside the radius but within 1.2x
    xs = [0.5 - r * f for f in (1.5, 0.95, 1.05, 0.95, 1.1, 0.97, 1.15)]
    assert [e["kind"] for e in drive(prox, xs)] == ["danger_enter"]


def test_unseen_robot_no_events():
    assert drive(Proximity(CFG), path(0.1, 0.9), seen=False) == []


def test_enter_cooldown_three_seconds():
    prox = Proximity(CFG)
    ev = drive(prox, [0.2, 0.5, 0.9, 0.5], dt=0.5)  # in, out, back in 1 s later
    assert [e["kind"] for e in ev] == ["danger_enter", "danger_exit"]
    ev = drive(prox, [0.9, 0.5], t0=5.0)
    assert [e["kind"] for e in ev] == ["danger_enter"]


def test_friendly_enter_and_clusters():
    prox = Proximity(CFG)
    ev = drive(prox, [0.5, 0.5], y=0.85)
    assert ev == [{"kind": "friendly_enter", "id": 6, "name": "Old Beacon", "role": "lighthouse"}]
    prox = Proximity(CFG)
    village = {"objects": [], "clusters": [{"id": 100001, "pos": [0.2, 0.2], "member_ids": [1, 2, 3],
                                            "role": "village", "name": "Little Hollow"}]}
    assert prox.update(robot(0.22, 0.2), village, 0)[0]["kind"] == "friendly_enter"


def test_threat_vanishing_sends_exit():
    prox = Proximity(CFG)
    prox.update(robot(0.5, 0.5), WORLD_OBJECTS, 0)
    ev = prox.update(robot(0.5, 0.5), {"objects": [TOWER], "clusters": []}, 0.1)
    assert ev == [{"kind": "danger_exit", "id": 5}]
