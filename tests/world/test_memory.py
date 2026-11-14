"""T49 — RoleMemory."""
from server.world.memory import RoleMemory

CASTLE = {"role": "castle", "name": "Old Keep", "behaviour": "neutral"}


def test_role_survives_other_world():
    mem = RoleMemory()
    mem.set("w-A", 7, CASTLE)
    mem.set("w-B", 7, {"role": "ship", "name": "The Salt Queen", "behaviour": "neutral"})
    mem.set("w-B", 8, {"role": "lighthouse", "name": "Old Beacon", "behaviour": "friendly"})
    assert mem.get("w-A", 7) == CASTLE
    assert mem.get("w-B", 7)["role"] == "ship"
    assert set(mem.roles_for("w-B")) == {7, 8}
    assert mem.get("w-A", 8) is None


def test_name_clash_gets_suffix():
    mem = RoleMemory()
    mem.set("w-A", 1, CASTLE)
    assert mem.set("w-A", 2, CASTLE)["name"] == "Old Keep II"
    assert mem.set("w-A", 3, CASTLE)["name"] == "Old Keep III"
    assert mem.get("w-A", 2)["role"] == "castle"  # sharing a role is fine
    assert mem.set("w-A", 1, CASTLE)["name"] == "Old Keep"  # re-setting itself is no clash
    assert mem.set("w-B", 2, CASTLE)["name"] == "Old Keep"  # other worlds are independent


def test_forget_object():
    mem = RoleMemory()
    mem.set("w-A", 1, CASTLE)
    mem.set("w-B", 1, CASTLE)
    mem.forget_object(1)
    assert mem.get("w-A", 1) is None and mem.get("w-B", 1) is None


def test_snapshot_roundtrip_and_clear(tmp_path):
    path = tmp_path / "runtime" / "memory.json"
    mem = RoleMemory(path)
    mem.set("w-A", 7, CASTLE)
    again = RoleMemory.load(path)
    assert again.get("w-A", 7) == CASTLE
    again.clear()
    assert not path.exists()
    assert again.roles_for("w-A") == {}
