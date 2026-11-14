from jetson.detector import Detection
from jetson.tracker import Tracker, iou

DT = 1 / 15


def box(cx, cy, w=40, h=40):
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]


def det(cx, cy, cls="cup", conf=0.9, w=40, h=40):
    return Detection(box(cx, cy, w, h), cls, conf)


def test_iou():
    assert iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1
    assert iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0
    assert abs(iou([0, 0, 10, 10], [5, 0, 15, 10]) - 1 / 3) < 1e-9


def test_one_id_for_object_moving_5px_per_frame():
    t = Tracker()
    ids = set()
    for i in range(100):
        out = t.update([det(100 + 5 * i, 300)], i * DT)
        assert len(out) == 1
        ids.add(out[0].id)
    assert ids == {1}


def test_crossing_objects_keep_ids():
    # Two same-class objects cross head-on, overlapping completely mid-way.
    t = Tracker()
    rightward_ids, leftward_ids = set(), set()
    for i in range(60):
        a = det(100 + 10 * i, 300)   # moving right
        b = det(700 - 10 * i, 300)   # moving left
        out = t.update([a, b], i * DT)
        assert len(out) == 2
        if abs(a.centre[0] - b.centre[0]) < 60:
            continue  # boxes overlap: which is which is ambiguous on this frame
        for tr in out:
            near_a = abs(tr.centre[0] - a.centre[0]) < abs(tr.centre[0] - b.centre[0])
            (rightward_ids if near_a else leftward_ids).add(tr.id)
    assert len(rightward_ids) == 1 and len(leftward_ids) == 1
    assert rightward_ids != leftward_ids


def test_ids_never_reused():
    t = Tracker(max_lost_s=0.2)
    first = t.update([det(100, 100)], 0.0)[0].id
    t.update([], 1.0)  # lost long enough to be dropped
    second = t.update([det(100, 100)], 1.1)[0].id
    assert second != first and second > first
    t.reset()
    assert t.update([det(100, 100)], 2.0)[0].id > second


def test_short_gap_keeps_id():
    t = Tracker(max_lost_s=1.0)
    tid = t.update([det(100, 100)], 0.0)[0].id
    assert t.update([], 0.3) == []
    assert t.update([det(103, 100)], 0.5)[0].id == tid


def test_class_majority_vote():
    t = Tracker()
    for i in range(10):
        out = t.update([det(200, 200, "cup")], i * DT)
    out = t.update([det(200, 200, "bowl")], 10 * DT)  # one-off misclassification
    assert out[0].cls == "cup"


def test_low_confidence_keeps_track_but_does_not_start_one():
    t = Tracker()
    assert t.update([det(300, 300, conf=0.3)], 0.0) == []
    tid = t.update([det(100, 100, conf=0.9)], DT)[0].id
    out = t.update([det(101, 100, conf=0.3)], 2 * DT)
    assert [o.id for o in out] == [tid]
