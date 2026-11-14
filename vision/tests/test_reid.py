import numpy as np

from vision.reid import ReId, compatible
from vision.tracker import Track

CFG = {"OBJECT_FORGET_S": 600.0}
W, H = 1280, 720


def tr(tid, cx, cy, cls="cup", w=80):
    return Track(tid, cls, [cx - w / 2, cy - w / 2, cx + w / 2, cy + w / 2], 0.9)


def scene(*items):
    """A frame with coloured squares: items are (cx, cy, bgr)."""
    f = np.full((H, W, 3), 40, np.uint8)
    for cx, cy, bgr in items:
        f[cy - 40:cy + 40, cx - 40:cx + 40] = bgr
        f[cy - 10:cy + 10, cx - 40:cx + 40] = (230, 230, 230)  # a white band, so histograms have some shape
    return f


RED, BLUE, GREEN = (0, 0, 220), (220, 0, 0), (0, 200, 0)


def test_object_back_in_view_after_a_turn_gets_its_old_id():
    reid = ReId(CFG)
    red_left = scene((300, 400, RED))
    assert [t.id for t in reid.apply([tr(7, 300, 400)], 0.0, red_left)] == [7]
    reid.apply([tr(7, 310, 400)], 0.1, scene((310, 400, RED)))
    reid.apply([], 1.0, scene())                  # the robot turned away
    reid.apply([], 30.0, scene())
    # 40 s later the cup comes back into view on the other side of the frame, with a new tracker id.
    back = reid.apply([tr(55, 1000, 300)], 40.0, scene((1000, 300, RED)))
    assert [t.id for t in back] == [7]
    assert [t.id for t in reid.apply([tr(55, 990, 300)], 40.1, scene((990, 300, RED)))] == [7]


def test_different_colours_are_different_objects():
    reid = ReId(CFG)
    reid.apply([tr(7, 300, 400)], 0.0, scene((300, 400, RED)))
    reid.apply([], 1.0, scene())
    out = reid.apply([tr(12, 300, 400)], 2.0, scene((300, 400, BLUE)))
    assert [t.id for t in out] == [12]


def test_incompatible_class_is_new_even_if_it_looks_the_same():
    reid = ReId(CFG)
    reid.apply([tr(7, 300, 400)], 0.0, scene((300, 400, RED)))
    reid.apply([], 1.0, scene())
    out = reid.apply([tr(12, 300, 400, cls="scissors")], 2.0, scene((300, 400, RED)))
    assert [t.id for t in out] == [12]


def test_forgotten_after_forget_s():
    reid = ReId({"OBJECT_FORGET_S": 10.0})
    reid.apply([tr(7, 300, 400)], 0.0, scene((300, 400, RED)))
    reid.apply([], 1.0, scene())
    assert reid.remembered == 1
    out = reid.apply([tr(12, 300, 400)], 20.0, scene((300, 400, RED)))
    assert [t.id for t in out] == [12] and reid.remembered == 0


def test_compatible_classes():
    assert compatible("cup", "bowl")
    assert compatible("object", "bottle")
    assert not compatible("cup", "scissors")


def test_best_match_wins_and_ids_stay_unique():
    reid = ReId(CFG)
    both = scene((300, 400, RED), (900, 400, GREEN))
    reid.apply([tr(1, 300, 400), tr(2, 900, 400)], 0.0, both)
    reid.apply([], 1.0, scene())
    # Both come back, swapped sides.
    swapped = scene((300, 400, GREEN), (900, 400, RED))
    out = reid.apply([tr(10, 300, 400), tr(11, 900, 400)], 5.0, swapped)
    assert [t.id for t in out] == [2, 1]


def test_an_id_in_view_is_never_given_to_a_second_track():
    reid = ReId(CFG)
    reid.apply([tr(1, 300, 400)], 0.0, scene((300, 400, RED)))
    reid.apply([], 1.0, scene())
    twins = scene((300, 400, RED), (900, 400, RED))
    out = reid.apply([tr(10, 300, 400), tr(11, 900, 400)], 2.0, twins)
    assert sorted(t.id for t in out) == [1, 11]


def test_without_frames_only_a_short_gap_at_the_same_spot_matches():
    reid = ReId(CFG)
    reid.apply([tr(7, 300, 400)], 0.0)
    reid.apply([], 0.5)
    assert [t.id for t in reid.apply([tr(12, 300, 400)], 1.0)] == [7]
    reid.apply([], 2.0)
    assert [t.id for t in reid.apply([tr(13, 300, 400)], 9.0)] == [13]  # too long ago to trust without colours


def test_reset_forgets():
    reid = ReId(CFG)
    reid.apply([tr(7, 300, 400)], 0.0, scene((300, 400, RED)))
    reid.apply([], 1.0, scene())
    reid.reset()
    assert [t.id for t in reid.apply([tr(12, 300, 400)], 2.0, scene((300, 400, RED)))] == [12]
