"""T57 — danger and friendly proximity events, judged from the robot's view."""
from server.world.proximity import Proximity

CFG = {"DANGER_SIZE": 0.35, "FRIENDLY_SIZE": 0.3, "NEAR_CM": 20}


def dragon(size, x=0.5, visible=True):
    return {"id": 5, "pos": [x, 0.6], "size": [size, size], "visible": visible, "role": "dragon", "name": "Ember",
            "behaviour": "threat"}


TOWER = {"id": 6, "pos": [0.5, 0.5], "size": [0.32, 0.5], "visible": True, "role": "lighthouse",
         "name": "Old Beacon", "behaviour": "friendly"}


def robot(distance=None, facing=None):
    return {"distance_cm": distance, "override": False, "facing_id": facing}


def approach(prox, sizes, x=0.5, t0=0.0, dt=0.1, robot_state=None):
    """The robot drives towards (or away from) the dragon: its size in the view changes."""
    events = []
    for i, s in enumerate(sizes):
        events += prox.update(robot_state or robot(), {"objects": [dragon(s, x)], "clusters": []}, t0 + i * dt)
    return events


def test_driving_up_to_a_threat_and_backing_off_one_enter_one_exit():
    sizes = [0.1 + 0.02 * i for i in range(20)] + [0.48 - 0.03 * i for i in range(16)]
    events = approach(Proximity(CFG), sizes)
    assert [e["kind"] for e in events] == ["danger_enter", "danger_exit"]
    assert events[0] == {"kind": "danger_enter", "id": 5, "name": "Ember", "role": "dragon"}


def test_hysteresis_near_the_threshold():
    # wobble just above / just below the threshold, but within 1.2x
    sizes = [0.2, 0.36, 0.33, 0.36, 0.31, 0.35, 0.30]
    assert [e["kind"] for e in approach(Proximity(CFG), sizes)] == ["danger_enter"]


def test_big_threat_off_to_the_side_is_not_ahead():
    assert approach(Proximity(CFG), [0.4, 0.45], x=0.95) == []


def test_ultrasonic_makes_the_faced_threat_near_even_if_small():
    prox = Proximity(CFG)
    ev = prox.update(robot(distance=15, facing=5), {"objects": [dragon(0.15)], "clusters": []}, 0.0)
    assert [e["kind"] for e in ev] == ["danger_enter"]
    other = Proximity(CFG)  # the sensor only speaks for the object being faced
    assert other.update(robot(distance=15, facing=9), {"objects": [dragon(0.15)], "clusters": []}, 0.0) == []


def test_out_of_view_threat_exits():
    prox = Proximity(CFG)
    prox.update(robot(), {"objects": [dragon(0.5)], "clusters": []}, 0.0)
    ev = prox.update(robot(), {"objects": [dragon(0.5, visible=False)], "clusters": []}, 0.1)
    assert ev == [{"kind": "danger_exit", "id": 5}]


def test_enter_cooldown_three_seconds():
    prox = Proximity(CFG)
    ev = approach(prox, [0.5, 0.1, 0.5], dt=0.5)  # in, out, back in 1 s later
    assert [e["kind"] for e in ev] == ["danger_enter", "danger_exit"]
    ev = approach(prox, [0.1, 0.5], t0=5.0)
    assert [e["kind"] for e in ev] == ["danger_enter"]


def test_friendly_enter_and_clusters():
    prox = Proximity(CFG)
    ev = prox.update(robot(), {"objects": [TOWER], "clusters": []}, 0)
    assert ev == [{"kind": "friendly_enter", "id": 6, "name": "Old Beacon", "role": "lighthouse"}]
    prox = Proximity(CFG)
    village = {"objects": [], "clusters": [{"id": 100001, "pos": [0.5, 0.6], "size": [0.6, 0.3],
                                            "member_ids": [1, 2, 3], "role": "village", "name": "Little Hollow"}]}
    assert prox.update(robot(), village, 0)[0]["kind"] == "friendly_enter"


def test_threat_vanishing_sends_exit():
    prox = Proximity(CFG)
    prox.update(robot(), {"objects": [dragon(0.5), TOWER], "clusters": []}, 0)
    ev = prox.update(robot(), {"objects": [TOWER], "clusters": []}, 0.1)
    assert ev == [{"kind": "danger_exit", "id": 5}]
