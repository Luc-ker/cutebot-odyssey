"""T51 — local fallback role picker."""
import pytest

from server.world import fallback_roles as fr
from server.world.fallback_roles import pick_role

STUB = [  # three-role stub (CONTRACTS C5) plus a threat
    {"role": "castle", "behaviour": "neutral", "worlds": ["kingdom"], "classes": ["chair"]},
    {"role": "lighthouse", "behaviour": "friendly", "worlds": ["ocean", "sea"], "classes": ["bottle"]},
    {"role": "ship", "behaviour": "neutral", "worlds": ["ocean"], "classes": ["shoe"]},
    {"role": "sea_serpent", "behaviour": "threat", "worlds": ["ocean"], "classes": ["remote"]},
    {"role": "giant", "behaviour": "neutral", "system_only": True, "worlds": ["*"], "classes": ["bottle"]},
]
OCEAN = {"id": "w-00000001", "world": {"name": "The Salt Sea", "setting": "open ocean", "mood": "adventurous"}}
OCEAN_ROLES = {"lighthouse", "ship", "boat", "harbour", "raft", "sea_serpent", "beacon", "island", "reef"}


def test_deterministic():
    a = [pick_role(OCEAN, "bottle", ["ship"], obj_id=12, vocab=STUB) for _ in range(5)]
    assert all(x == a[0] for x in a)
    assert a[0]["name"]


def test_bottle_in_ocean_world_stub():
    assert pick_role(OCEAN, "bottle", [], obj_id=3, vocab=STUB)["role"] == "lighthouse"


def test_bottle_in_ocean_world_shipped_vocab():
    vocab = fr.load_vocab()
    if vocab is fr.DEFAULT_VOCAB:
        pytest.skip("shared/roles.json (T03) not shipped yet; checking the built-in list")
    assert pick_role(OCEAN, "bottle", [], obj_id=3, vocab=vocab)["role"] in OCEAN_ROLES


def test_bottle_in_ocean_world_builtin_vocab():
    assert pick_role(OCEAN, "bottle", [], obj_id=3, vocab=fr.DEFAULT_VOCAB)["role"] in OCEAN_ROLES


def test_never_picks_system_roles():
    for i in range(30):
        assert pick_role(OCEAN, "bottle", [], obj_id=i, vocab=STUB)["role"] != "giant"


def test_threat_limit_unless_dark():
    # one threat already among three objects -> fourth object may not be a second threat
    taken = ["sea_serpent", "ship", "lighthouse"]
    assert pick_role(OCEAN, "remote", taken, obj_id=4, vocab=STUB)["behaviour"] != "threat"
    dark = {"world": dict(OCEAN["world"], mood="dark and ominous")}
    assert pick_role(dark, "remote", taken, obj_id=4, vocab=STUB)["role"] == "sea_serpent"


def test_prefers_untaken_roles():
    first = pick_role(OCEAN, "cup", [], obj_id=1, vocab=STUB)["role"]
    second = pick_role(OCEAN, "cup", [first], obj_id=1, vocab=STUB)["role"]
    assert first != second
