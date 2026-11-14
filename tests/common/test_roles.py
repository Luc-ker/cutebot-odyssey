import json
from pathlib import Path

import pytest

ROLES_PATH = Path(__file__).resolve().parents[2] / "shared" / "roles.json"
ROLES = json.loads(ROLES_PATH.read_text())
BY_ROLE = {r["role"]: r for r in ROLES}

SECTION_8 = """castle palace fortress temple skyscraper tower watchtower lighthouse beacon village market harbour camp
ship raft boat forest grove jungle_patch mountain volcano cliff glacier river bridge road treasure relic crystal
dragon sea_serpent lava_beast yeti robot_sentinel giant""".split()

# §7.6 example worlds -> the setting keyword(s) a role may list for it.
EXAMPLE_WORLDS = {
    "open ocean": {"ocean", "sea"},
    "volcanic wasteland": {"wasteland", "volcanic"},
    "snowy night village": {"snow"},
    "kingdom": {"kingdom"},
    "neon city": {"neon city"},
    "rainforest": {"jungle", "rainforest"},
    "royal court": {"royal court"},
    "space station": {"space station", "space"},
}


def test_roles_are_unique():
    names = [r["role"] for r in ROLES]
    assert len(names) == len(set(names))


def test_every_section_8_role_present():
    missing = [r for r in SECTION_8 if r not in BY_ROLE]
    assert not missing


def test_at_least_ten_extra_roles():
    assert len(ROLES) >= len(SECTION_8) + 10


@pytest.mark.parametrize("role", ROLES, ids=lambda r: r["role"])
def test_role_fields(role):
    assert role["behaviour"] in {"friendly", "neutral", "threat"}
    assert role["prompt"].strip()
    assert role["icon"].strip()
    assert role["sfx"].strip()
    assert role["worlds"] and all(isinstance(w, str) and w for w in role["worlds"])
    assert isinstance(role["classes"], list)
    assert role["role"] == role["role"].lower() and " " not in role["role"]


def test_giant_is_system_only():
    assert BY_ROLE["giant"].get("system_only") is True
    assert [r["role"] for r in ROLES if r.get("system_only")] == ["giant"]


def test_at_least_four_threats():
    threats = [r for r in ROLES if r["behaviour"] == "threat" and not r.get("system_only")]
    assert len(threats) >= 4


@pytest.mark.parametrize("world, keywords", EXAMPLE_WORLDS.items())
def test_every_example_world_has_five_roles(world, keywords):
    listing = [r["role"] for r in ROLES if not r.get("system_only") and keywords & set(r["worlds"])]
    assert len(listing) >= 5, (world, listing)


@pytest.mark.parametrize("world, keywords", EXAMPLE_WORLDS.items())
def test_every_example_world_has_a_threat(world, keywords):
    assert any(r["behaviour"] == "threat" and keywords & set(r["worlds"])
               for r in ROLES if not r.get("system_only")), world


def test_every_non_system_role_suits_some_class():
    assert all(r["classes"] for r in ROLES if not r.get("system_only"))
