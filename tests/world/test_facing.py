"""T56 — facing-object detection (the object near the middle of the robot's view)."""
import math

from server.world.facing import FacingTracker, facing

CFG = {"FACING_HALF_ANGLE_DEG": 15, "FACING_MIN_SIZE": 0.08, "CAMERA_HFOV_DEG": 60}


def obj(i, x, size=0.2, visible=True, y=0.5):
    return {"id": i, "pos": [x, y], "size": [size, size], "visible": visible}


def test_centred_object_is_faced():
    t = FacingTracker(CFG)
    assert t.update([obj(4, 0.5)]) == 4
    assert t.update([obj(4, 0.6)]) == 4      # a little to the right is still ahead


def test_off_to_the_side_is_not_faced():
    t = FacingTracker(CFG)
    assert t.update([obj(4, 0.9)]) is None   # ~24 degrees right with a 60 degree camera
    assert t.update([obj(4, 0.05)]) is None


def test_small_far_away_and_out_of_view_are_not_faced():
    t = FacingTracker(CFG)
    assert t.update([obj(1, 0.5, size=0.03)]) is None
    assert t.update([obj(1, 0.5, visible=False)]) is None


def test_nearest_wins():
    t = FacingTracker(CFG)
    objs = [obj(1, 0.5, size=0.1), obj(2, 0.52, size=0.4)]
    assert t.update(objs) == 2


def test_centred_beats_slightly_bigger_but_off_centre():
    t = FacingTracker(CFG)
    objs = [obj(1, 0.5, size=0.2), obj(2, 0.62, size=0.22)]
    assert t.update(objs) == 1


def test_no_flicker_between_similar_targets():
    t = FacingTracker(CFG)
    seen = []
    for i in range(40):
        wobble = 0.02 * math.sin(i / 3)  # the robot wobbles a little while driving
        seen.append(t.update([obj(1, 0.47 + wobble), obj(2, 0.53 + wobble)]))
    switches = sum(1 for a, b in zip(seen, seen[1:]) if a != b)
    assert switches <= 1


def test_switches_when_clearly_better():
    t = FacingTracker(CFG)
    t.current = 1
    assert t.update([obj(1, 0.5, size=0.1), obj(2, 0.5, size=0.3)]) == 2


def test_clusters_are_targets():
    t = FacingTracker(CFG)
    clusters = [{"id": 100001, "pos": [0.5, 0.5], "member_ids": [1, 2, 3]}]
    assert t.update([], clusters) == 100001


def test_module_function_and_nothing_in_view():
    assert facing([]) is None
    assert facing([{"id": 1, "pos": None}]) is None
