"""T52 — clustering."""
from server.world.clusters import CLUSTER_ID_BASE, ClusterTracker, find_clusters, name_cluster, reset

CM = 1 / 100  # table units per cm on a 100 cm table


def obj(i, x, y, s=0.0):
    return {"id": i, "pos": [x, y], "size": [s, s]}


def three_and_one(dx=0.0):
    return [obj(1, 0.2 + dx, 0.2), obj(2, 0.23, 0.2), obj(3, 0.26, 0.2), obj(4, 0.8, 0.8)]


def test_three_close_one_far():
    reset()
    clusters = find_clusters(three_and_one(), max_gap=4 * CM)
    assert len(clusters) == 1
    assert clusters[0].member_ids == [1, 2, 3]
    assert abs(clusters[0].pos[0] - 0.23) < 1e-9
    assert clusters[0].id > CLUSTER_ID_BASE


def test_needs_three_members():
    assert ClusterTracker().update([obj(1, 0.2, 0.2), obj(2, 0.22, 0.2)], 4 * CM) == []


def test_gap_uses_footprints():
    # centres 10 cm apart but 8 cm wide objects -> 2 cm gap
    objs = [obj(1, 0.1, 0.5, 0.08), obj(2, 0.2, 0.5, 0.08), obj(3, 0.3, 0.5, 0.08)]
    assert len(ClusterTracker().update(objs, 3 * CM)) == 1


def test_id_stable_when_a_member_moves():
    t = ClusterTracker()
    first = t.update(three_and_one(), 4 * CM)[0].id
    assert t.update(three_and_one(dx=0.005), 4 * CM)[0].id == first
    # one member swapped for a new object (2/3 overlap) keeps the id
    swapped = [obj(1, 0.2, 0.2), obj(2, 0.23, 0.2), obj(5, 0.26, 0.2)]
    assert t.update(swapped, 4 * CM)[0].id == first


def test_new_cluster_new_id():
    t = ClusterTracker()
    a = t.update(three_and_one(), 4 * CM)[0].id
    other = [obj(7, 0.7, 0.7), obj(8, 0.73, 0.7), obj(9, 0.76, 0.7)]
    assert t.update(other, 4 * CM)[0].id != a


def test_place_role_from_setting():
    c = ClusterTracker().update(three_and_one(), 4 * CM)[0]
    assert name_cluster(c, {"world": {"setting": "open ocean"}}).role == "harbour"
    assert name_cluster(c, {"world": {"setting": "medieval kingdom"}}).role == "village"
    assert c.name
