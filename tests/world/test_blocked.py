"""T60 — physical-block detection."""
from server.world.blocked import BlockedDetector, obstacle_word

CFG = {"SAFETY_STOP_CM": 8, "TABLE_W_CM": 100, "TABLE_H_CM": 100}
OCEAN = {"world": {"setting": "open ocean"}}


def state(d, x=0.5, facing=None):
    return {"pos": [x, 0.5], "heading": 0, "seen": True, "distance_cm": d, "override": False, "facing_id": facing}


def run(det, states, dt=0.1, world=OCEAN, names=None, t0=0.0):
    out = []
    for i, s in enumerate(states):
        ev = det.update(s, t0 + i * dt, world, names)
        if ev:
            out.append(ev)
    return out


def test_sustained_close_and_still_one_event():
    det = BlockedDetector(CFG)
    assert run(det, [state(6)] * 30) == [{"kind": "blocked", "obstacle": "reef"}]


def test_uses_facing_name():
    det = BlockedDetector(CFG)
    ev = run(det, [state(6, facing=4)] * 15, names={4: "The Salt Queen"})
    assert ev == [{"kind": "blocked", "obstacle": "The Salt Queen"}]


def test_moving_robot_is_not_blocked():
    det = BlockedDetector(CFG)
    assert run(det, [state(6, x=0.3 + i * 0.015) for i in range(30)]) == []


def test_far_or_unknown_distance_not_blocked():
    det = BlockedDetector(CFG)
    assert run(det, [state(11)] * 30) == []
    assert run(det, [state(None)] * 30) == []


def test_brief_close_not_blocked():
    det = BlockedDetector(CFG)
    assert run(det, [state(6)] * 8 + [state(30)] + [state(6)] * 8) == []


def test_cooldown_six_seconds():
    det = BlockedDetector(CFG)
    assert len(run(det, [state(6)] * 15)) == 1
    assert run(det, [state(30)] + [state(6)] * 15, t0=2.0) == []
    assert len(run(det, [state(30)] + [state(6)] * 15, t0=8.0)) == 1


def test_setting_words():
    assert obstacle_word({"world": {"setting": "volcanic wasteland"}}) == "lava wall"
    assert obstacle_word({"world": {"setting": "snowy night village"}}) == "ice cliff"
    assert obstacle_word({"world": {"setting": "kingdom"}}) == "wall"
    assert obstacle_word(None) == "wall"
