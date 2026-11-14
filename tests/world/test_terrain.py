"""T53 — terrain words."""
from server.world.terrain import analyse

OCEAN = {"world": {"setting": "open ocean"}, "terrain": {"open_space": "open sea", "under_table": "the deep sea"}}


def test_world_terrain_wins():
    out = analyse([{"id": 1, "pos": [0.5, 0.5], "size": [0.1, 0.1]}], OCEAN)
    assert out == {"open_space": "open sea", "under_table": "the deep sea"}


def test_defaults_from_setting_when_terrain_missing():
    out = analyse([], {"world": {"setting": "volcanic wasteland"}})
    assert out["under_table"] == "a lava cave"
    assert analyse([], {})["open_space"]
