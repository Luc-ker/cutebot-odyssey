from server.common.schemas import validate_world
from server.world.fallback_worlds import FALLBACK_WORLD_ORDER, load_fallback_worlds


def test_all_eight_fallbacks_validate_have_unique_names_and_known_colours():
    worlds = load_fallback_worlds()

    assert len(worlds) == 8
    assert [world["key"] for world in worlds] == list(FALLBACK_WORLD_ORDER)
    assert len({world["world"]["name"].casefold() for world in worlds}) == 8
    assert all(not validate_world(world) for world in worlds)
    assert all(world["roles"] == [] for world in worlds)