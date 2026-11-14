"""T56 — facing-object detection."""
import math

from server.world.facing import FacingTracker, facing

CFG = {"FACING_HALF_ANGLE_DEG": 25, "FACING_MAX_DIST": 0.35}


def robot(x, y, heading):
    return {"pos": [x, y], "heading": heading, "seen": True}


def test_straight_ahead_and_behind():
    t = FacingTracker(CFG)
    ahead = [{"id": 4, "pos": [0.7, 0.5]}]
    assert t.update(robot(0.5, 0.5, 0.0), ahead) == 4
    behind = [{"id": 4, "pos": [0.3, 0.5]}]
    assert t.update(robot(0.5, 0.5, 0.0), behind) is None


def test_out_of_range_and_outside_cone():
    t = FacingTracker(CFG)
    assert t.update(robot(0.1, 0.5, 0.0), [{"id": 1, "pos": [0.9, 0.5]}]) is None
    assert t.update(robot(0.5, 0.5, 0.0), [{"id": 1, "pos": [0.6, 0.7]}]) is None  # ~63 degrees off


def test_heading_convention_y_down():
    # heading +pi/2 points along +y (down the table)
    t = FacingTracker(CFG)
    assert t.update(robot(0.5, 0.3, math.pi / 2), [{"id": 2, "pos": [0.5, 0.5]}]) == 2


def test_nearest_wins():
    t = FacingTracker(CFG)
    objs = [{"id": 1, "pos": [0.8, 0.5]}, {"id": 2, "pos": [0.6, 0.5]}]
    assert t.update(robot(0.5, 0.5, 0.0), objs) == 2


def test_no_flicker_between_similar_targets():
    t = FacingTracker(CFG)
    objs = [{"id": 1, "pos": [0.7, 0.47]}, {"id": 2, "pos": [0.7, 0.53]}]
    seen = []
    for i in range(40):
        heading = 0.05 * math.sin(i / 3)  # small wobble around straight ahead
        seen.append(t.update(robot(0.5, 0.5, heading), objs))
    switches = sum(1 for a, b in zip(seen, seen[1:]) if a != b)
    assert switches <= 1


def test_switches_when_clearly_better():
    t = FacingTracker(CFG)
    objs = [{"id": 1, "pos": [0.7, 0.5]}, {"id": 2, "pos": [0.6, 0.5]}]
    t.current = 1
    assert t.update(robot(0.5, 0.5, 0.0), objs) == 2


def test_clusters_are_targets():
    t = FacingTracker(CFG)
    clusters = [{"id": 100001, "pos": [0.65, 0.5], "member_ids": [1, 2, 3]}]
    assert t.update(robot(0.5, 0.5, 0.0), [], clusters) == 100001


def test_module_function_and_missing_pose():
    assert facing({"pos": None, "heading": None}, [{"id": 1, "pos": [0.5, 0.5]}]) is None
