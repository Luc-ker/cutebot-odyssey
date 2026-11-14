"""T61 — giant enter and leave events."""
from server.world.giants import GiantTracker

HAND = {"id": 1, "kind": "hand", "pos": [0.5, 0.1], "size": [0.2, 0.2], "edge": "top"}


def test_flicker_gives_one_enter_and_one_leave():
    t = GiantTracker()
    events = []
    now = 0.0
    for i in range(30):  # in/out every 100 ms for 3 s
        events += t.update([dict(HAND, id=i)] if i % 2 == 0 else [], now)
        now += 0.1
    for _ in range(12):  # gone
        events += t.update([], now)
        now += 0.1
    kinds = [e["kind"] for e in events]
    assert kinds == ["giant_enter", "giant_leave"]
    assert events[0]["giant_kind"] == "hand" and events[0]["edge"] == "top"
    assert events[0]["id"] == events[1]["id"] and events[0]["id"].startswith("g")


def test_needs_300ms_presence():
    t = GiantTracker()
    assert t.update([HAND], 0.0) == []
    assert t.update([HAND], 0.2) == []
    assert [e["kind"] for e in t.update([HAND], 0.3)] == ["giant_enter"]


def test_single_frame_blip_never_enters():
    t = GiantTracker()
    events = t.update([HAND], 0.0)
    for i in range(1, 15):
        events += t.update([], i * 0.1)
    assert events == []


def test_leave_after_800ms_via_tick():
    t = GiantTracker()
    for i in range(5):
        t.update([HAND], i * 0.1)
    assert t.tick(1.1) == []
    assert [e["kind"] for e in t.tick(1.25)] == ["giant_leave"]


def test_two_edges_are_two_giants():
    t = GiantTracker()
    other = {"kind": "person", "pos": [0.5, 0.9], "edge": "bottom"}
    events = []
    for i in range(5):
        events += t.update([HAND, other], i * 0.1)
    enters = [e for e in events if e["kind"] == "giant_enter"]
    assert len(enters) == 2 and {e["edge"] for e in enters} == {"top", "bottom"}


def test_moving_hand_keeps_its_id():
    t = GiantTracker()
    events = []
    for i in range(10):
        events += t.update([dict(HAND, pos=[0.3 + 0.03 * i, 0.15])], i * 0.1)
    assert len([e for e in events if e["kind"] == "giant_enter"]) == 1
