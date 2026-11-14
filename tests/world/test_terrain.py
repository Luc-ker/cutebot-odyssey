"""T53 — terrain analysis."""
from server.world.terrain import analyse

OCEAN = {"world": {"setting": "open ocean"}, "terrain": {"open_space": "open sea", "under_table": "the deep sea"}}


def _overlaps(r, x0, y0, x1, y1):
    eps = 1e-9
    return r["x"] < x1 - eps and r["x"] + r["w"] > x0 + eps and r["y"] < y1 - eps and r["y"] + r["h"] > y0 + eps


def test_empty_table_one_full_region():
    out = analyse([], OCEAN)
    assert out["open_regions"] == [{"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}]
    assert out["open_space"] == "open sea" and out["under_table"] == "the deep sea"


def test_regions_avoid_central_object():
    objs = [{"id": 1, "pos": [0.5, 0.5], "size": [0.1, 0.1]}]
    regions = analyse(objs, OCEAN)["open_regions"]
    assert 1 <= len(regions) <= 3
    for r in regions:
        assert not _overlaps(r, 0.45, 0.45, 0.55, 0.55)
    areas = [r["w"] * r["h"] for r in regions]
    assert areas == sorted(areas, reverse=True) and areas[0] >= 0.4


def test_regions_do_not_overlap_each_other():
    objs = [{"id": 1, "pos": [0.3, 0.3], "size": [0.1, 0.1]}, {"id": 2, "pos": [0.7, 0.6], "size": [0.2, 0.1]}]
    rs = analyse(objs, OCEAN)["open_regions"]
    for i, a in enumerate(rs):
        for b in rs[i + 1:]:
            assert not _overlaps(a, b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"])


def test_defaults_from_setting_when_terrain_missing():
    out = analyse([], {"world": {"setting": "volcanic wasteland"}})
    assert out["under_table"] == "a lava cave"
    assert analyse([], {})["open_space"]
